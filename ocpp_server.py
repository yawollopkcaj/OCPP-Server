import asyncio
import logging
import json
import websockets
from datetime import datetime
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ocpp-server')

# Store connected charging stations
charge_points = {}

class OCPPServer:
    def __init__(self, host='localhost', port=9000):
        self.host = host
        self.port = port
        self.server = None
    
    async def start(self):
        """Start the OCPP server"""
        self.server = await websockets.serve(self.on_connect, self.host, self.port)
        logger.info(f"OCPP Server started on ws://{self.host}:{self.port}")
        await self.server.wait_closed()
    
    async def on_connect(self, websocket, path):
    """Handle new charge point connections"""
    try:
        # Use the 'path' parameter directly instead of websocket.path.
        # Expected path format: /ocpp/charge_point_id
        parts = path.split('/')
        charge_point_id = parts[-1] if len(parts) > 1 else "unknown"
        
        logger.info(f"Charge point {charge_point_id} connected from path: {path}")
        
        # Register the charge point
        charge_points[charge_point_id] = {
            'websocket': websocket,
            'connected_at': datetime.now(),
            'status': 'Available'
        }
        
        # Handle messages
        await self.handle_messages(websocket, charge_point_id)
    except Exception as e:
        logger.error(f"Error handling connection: {e}")

    
    async def handle_messages(self, websocket, charge_point_id):
        """Process messages from a charge point"""
        try:
            async for message in websocket:
                await self.process_message(websocket, charge_point_id, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for charge point {charge_point_id}")
        finally:
            # Remove charge point on disconnect
            if charge_point_id in charge_points:
                del charge_points[charge_point_id]
    
    async def process_message(self, websocket, charge_point_id, message):
        """Process an OCPP message"""
        try:
            msg = json.loads(message)
            
            # OCPP message format: [MessageTypeId, UniqueId, Action, Payload]
            message_type_id = msg[0]
            unique_id = msg[1]
            
            if message_type_id == 2:  # CALL
                action = msg[2]
                payload = msg[3] if len(msg) > 3 else {}
                logger.info(f"Received {action} message from {charge_point_id}")
                await self.handle_call(websocket, charge_point_id, unique_id, action, payload)
            elif message_type_id == 3:  # CALLRESULT
                payload = msg[2]
                logger.info(f"Received CALLRESULT from {charge_point_id}: {unique_id}")
                await self.handle_call_result(charge_point_id, unique_id, payload)
            elif message_type_id == 4:  # CALLERROR
                payload = msg[2]
                logger.info(f"Received CALLERROR from {charge_point_id}: {unique_id}")
                await self.handle_call_error(charge_point_id, unique_id, payload)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message: {message}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def handle_call(self, websocket, charge_point_id, unique_id, action, payload):
        """Handle incoming CALL messages from charge points"""
        response = None
        
        # Process different OCPP actions
        if action == "BootNotification":
            response = self.handle_boot_notification(charge_point_id, payload)
        elif action == "Heartbeat":
            response = self.handle_heartbeat()
        elif action == "StatusNotification":
            response = self.handle_status_notification(charge_point_id, payload)
        elif action == "Authorize":
            response = self.handle_authorize(payload)
        elif action == "StartTransaction":
            response = self.handle_start_transaction(charge_point_id, payload)
        elif action == "StopTransaction":
            response = self.handle_stop_transaction(charge_point_id, payload)
        elif action == "MeterValues":
            response = self.handle_meter_values(charge_point_id, payload)
        else:
            # Generic response for unhandled actions
            logger.warning(f"Unhandled action: {action}")
            response = {}
        
        # Send response
        callresult = [3, unique_id, response]  # CALLRESULT message
        await websocket.send(json.dumps(callresult))
    
    async def handle_call_result(self, charge_point_id, unique_id, payload):
        """Handle CALLRESULT messages (responses to our requests)"""
        logger.info(f"Received CALLRESULT from {charge_point_id} with ID {unique_id}: {payload}")
    
    async def handle_call_error(self, charge_point_id, unique_id, payload):
        """Handle CALLERROR messages (error responses to our requests)"""
        logger.error(f"Received CALLERROR from {charge_point_id} with ID {unique_id}: {payload}")
    
    def handle_boot_notification(self, charge_point_id, payload):
        """Process BootNotification request"""
        logger.info(f"Boot notification from {charge_point_id}: {payload}")
        return {
            "status": "Accepted",
            "currentTime": datetime.utcnow().isoformat(),
            "interval": 300  # Heartbeat interval in seconds
        }
    
    def handle_heartbeat(self):
        """Process Heartbeat request"""
        return {
            "currentTime": datetime.utcnow().isoformat()
        }
    
    def handle_status_notification(self, charge_point_id, payload):
        """Process StatusNotification request"""
        if charge_point_id in charge_points:
            charge_points[charge_point_id]['status'] = payload.get('status', 'Unknown')
        logger.info(f"Status update from {charge_point_id}: {payload.get('status', 'Unknown')}")
        return {}  # Empty response for StatusNotification
    
    def handle_authorize(self, payload):
        """Process Authorize request"""
        id_tag = payload.get('idTag', '')
        logger.info(f"Authorization request for tag: {id_tag}")
        # In a real system, validate the ID tag against a database
        return {
            "idTagInfo": {
                "status": "Accepted",
                "expiryDate": (datetime.utcnow().replace(year=datetime.utcnow().year + 1)).isoformat()
            }
        }
    
    def handle_start_transaction(self, charge_point_id, payload):
        """Process StartTransaction request"""
        id_tag = payload.get('idTag', '')
        meter_start = payload.get('meterStart', 0)
        transaction_id = int(uuid4().int % 1000000)  # Generate a transaction ID
        logger.info(f"Transaction started by {charge_point_id}, tag: {id_tag}, meter: {meter_start}")
        return {
            "transactionId": transaction_id,
            "idTagInfo": {
                "status": "Accepted"
            }
        }
    
    def handle_stop_transaction(self, charge_point_id, payload):
        """Process StopTransaction request"""
        transaction_id = payload.get('transactionId', 0)
        meter_stop = payload.get('meterStop', 0)
        logger.info(f"Transaction {transaction_id} stopped by {charge_point_id}, meter: {meter_stop}")
        return {
            "idTagInfo": {
                "status": "Accepted"
            }
        }
    
    def handle_meter_values(self, charge_point_id, payload):
        """Process MeterValues request"""
        transaction_id = payload.get('transactionId', 0)
        values = payload.get('meterValue', [])
        logger.info(f"Meter values from {charge_point_id} for transaction {transaction_id}: {values}")
        return {}  # Empty response for MeterValues
    
    async def send_request(self, charge_point_id, action, payload):
        """Send a request to a specific charge point"""
        if charge_point_id not in charge_points:
            logger.error(f"Charge point {charge_point_id} not connected")
            return None
        
        websocket = charge_points[charge_point_id]['websocket']
        message_id = str(uuid4())
        request = [2, message_id, action, payload]  # CALL message
        
        try:
            await websocket.send(json.dumps(request))
            logger.info(f"Sent {action} request to {charge_point_id}")
            return message_id
        except Exception as e:
            logger.error(f"Error sending request to {charge_point_id}: {e}")
            return None

# Server management functions
async def list_charge_points():
    """List all connected charge points and their status"""
    result = []
    for cp_id, data in charge_points.items():
        result.append({
            "id": cp_id,
            "status": data['status'],
            "connected_since": data['connected_at'].isoformat()
        })
    return result

async def remote_start_transaction(charge_point_id, id_tag):
    """Remotely start a charging transaction"""
    if charge_point_id not in charge_points:
        return {"error": "Charge point not connected"}
    
    server = OCPPServer()  # Create a server instance just to use the send_request method
    message_id = await server.send_request(charge_point_id, "RemoteStartTransaction", {
        "idTag": id_tag
    })
    
    return {"message_id": message_id}

async def remote_stop_transaction(charge_point_id, transaction_id):
    """Remotely stop a charging transaction"""
    if charge_point_id not in charge_points:
        return {"error": "Charge point not connected"}
    
    server = OCPPServer()
    message_id = await server.send_request(charge_point_id, "RemoteStopTransaction", {
        "transactionId": transaction_id
    })
    
    return {"message_id": message_id}

# Main function to run the server
async def main():
    # Start the OCPP server
    server = OCPPServer(host='0.0.0.0', port=9000)
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())