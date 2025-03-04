import asyncio
import websockets
import json
import logging
import random
import time
from datetime import datetime
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ocpp-charger')

class ChargePoint:
    def __init__(self, cp_id, server_url):
        self.cp_id = cp_id
        self.server_url = server_url
        self.ws = None
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.pending_requests = {}
        self.transaction_id = None
        self.authorized_tags = ["ABC123", "DEF456", "GHI789"]  # Sample RFID tags
        self.model = "TestCharger-2000"
        self.vendor = "OCPP Test Systems"
        self.firmware_version = "1.0.0"
    
    async def connect(self):
        """Connect to the OCPP server"""
        # Full URL including the charge point ID
        url = f"{self.server_url}/{self.cp_id}"
        
        while self.connection_attempts < self.max_connection_attempts:
            try:
                self.connection_attempts += 1
                logger.info(f"Connecting to {url}, attempt {self.connection_attempts}")
                
                self.ws = await websockets.connect(url)
                logger.info(f"Connected to OCPP server: {url}")
                
                # After connection, send boot notification
                await self.send_boot_notification()
                
                # Start message handling
                await self.message_handler()
                
                # If we get here, the connection was closed
                logger.info("Connection closed")
                
            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)  # Wait before retrying
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(5)
    
    async def message_handler(self):
        """Handle incoming messages from the server"""
        try:
            async for message in self.ws:
                await self.process_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection to server closed")
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
    
    async def process_message(self, message):
        """Process incoming OCPP messages"""
        try:
            msg = json.loads(message)
            message_type_id = msg[0]
            
            if message_type_id == 2:  # CALL from server
                await self.handle_call(msg)
            elif message_type_id == 3:  # CALLRESULT (response to our call)
                await self.handle_call_result(msg)
            elif message_type_id == 4:  # CALLERROR
                await self.handle_call_error(msg)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON message: {message}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def handle_call(self, msg):
        """Handle CALL messages from the server"""
        message_id = msg[1]
        action = msg[2]
        payload = msg[3] if len(msg) > 3 else {}
        
        logger.info(f"Received {action} request from server: {payload}")
        
        response = {}
        
        # Handle different actions from the server
        if action == "Reset":
            response = {"status": "Accepted"}
            # Simulate reset behavior
            logger.info(f"Simulating {payload.get('type', 'Soft')} reset")
            
        elif action == "RemoteStartTransaction":
            id_tag = payload.get("idTag")
            response = {"status": "Accepted"}
            # Start a transaction
            if id_tag:
                await self.simulate_transaction_start(id_tag)
            
        elif action == "RemoteStopTransaction":
            transaction_id = payload.get("transactionId")
            response = {"status": "Accepted"}
            # Stop the transaction
            if transaction_id and self.transaction_id:
                await self.simulate_transaction_stop()
            
        elif action == "GetConfiguration":
            response = {
                "configurationKey": [
                    {"key": "HeartbeatInterval", "readonly": False, "value": "300"},
                    {"key": "ConnectionTimeOut", "readonly": True, "value": "30"}
                ]
            }
        
        # Send response back to server
        callresult = [3, message_id, response]
        await self.ws.send(json.dumps(callresult))
    
    async def handle_call_result(self, msg):
        """Handle CALLRESULT messages (responses to our requests)"""
        message_id = msg[1]
        payload = msg[2]
        
        if message_id in self.pending_requests:
            action = self.pending_requests[message_id]
            logger.info(f"Received response for {action}: {payload}")
            
            # Process specific responses
            if action == "BootNotification":
                # Schedule heartbeat based on interval
                interval = payload.get("interval", 300)
                asyncio.create_task(self.heartbeat_cycle(interval))
                
                # Send status notification after boot
                await self.send_status_notification("Available")
                
                # Start simulation
                asyncio.create_task(self.simulate_charging_cycle())
            
            elif action == "StartTransaction" and "transactionId" in payload:
                # Store the transaction ID from the server
                self.transaction_id = payload["transactionId"]
                logger.info(f"Transaction started with ID: {self.transaction_id}")
            
            # Clean up
            del self.pending_requests[message_id]
        else:
            logger.warning(f"Received response for unknown message ID: {message_id}")
    
    async def handle_call_error(self, msg):
        """Handle CALLERROR messages"""
        message_id = msg[1]
        error_details = msg[2]
        
        if message_id in self.pending_requests:
            action = self.pending_requests[message_id]
            logger.error(f"Received error for {action}: {error_details}")
            del self.pending_requests[message_id]
        else:
            logger.error(f"Received error for unknown message ID: {message_id}")
    
    async def send_request(self, action, payload):
        """Send an OCPP request to the server"""
        message_id = str(uuid4())
        request = [2, message_id, action, payload]
        self.pending_requests[message_id] = action
        
        await self.ws.send(json.dumps(request))
        logger.info(f"Sent {action} request: {payload}")
        return message_id
    
    async def send_boot_notification(self):
        """Send BootNotification to the server"""
        await self.send_request("BootNotification", {
            "chargePointVendor": self.vendor,
            "chargePointModel": self.model,
            "chargePointSerialNumber": f"CP{random.randint(10000, 99999)}",
            "chargeBoxSerialNumber": f"CB{random.randint(10000, 99999)}",
            "firmwareVersion": self.firmware_version,
            "iccid": "",
            "imsi": "",
            "meterType": "Test Meter",
            "meterSerialNumber": f"M{random.randint(10000, 99999)}"
        })
    
    async def send_heartbeat(self):
        """Send Heartbeat to the server"""
        await self.send_request("Heartbeat", {})
    
    async def send_status_notification(self, status):
        """Send StatusNotification to the server"""
        await self.send_request("StatusNotification", {
            "connectorId": 1,
            "errorCode": "NoError",
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def send_authorize(self, id_tag):
        """Send Authorize request"""
        await self.send_request("Authorize", {
            "idTag": id_tag
        })
    
    async def send_start_transaction(self, id_tag):
        """Send StartTransaction request"""
        await self.send_request("StartTransaction", {
            "connectorId": 1,
            "idTag": id_tag,
            "meterStart": random.randint(10000, 20000),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def send_stop_transaction(self, meter_stop):
        """Send StopTransaction request"""
        await self.send_request("StopTransaction", {
            "transactionId": self.transaction_id,
            "meterStop": meter_stop,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": "Local"
        })
        self.transaction_id = None
    
    async def send_meter_values(self):
        """Send MeterValues to the server"""
        if not self.transaction_id:
            return
        
        await self.send_request("MeterValues", {
            "connectorId": 1,
            "transactionId": self.transaction_id,
            "meterValue": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "sampledValue": [
                        {
                            "value": str(random.randint(1, 30)),
                            "context": "Sample.Periodic",
                            "format": "Raw",
                            "measurand": "Power.Active.Import",
                            "location": "Outlet",
                            "unit": "kW"
                        },
                        {
                            "value": str(random.randint(100, 500) / 10),
                            "context": "Sample.Periodic",
                            "format": "Raw",
                            "measurand": "Current.Import",
                            "location": "Outlet",
                            "unit": "A"
                        }
                    ]
                }
            ]
        })
    
    async def heartbeat_cycle(self, interval):
        """Send heartbeats at the specified interval"""
        logger.info(f"Starting heartbeat cycle every {interval} seconds")
        while True:
            try:
                await asyncio.sleep(interval)
                await self.send_heartbeat()
            except websockets.exceptions.ConnectionClosed:
                logger.info("Connection closed, stopping heartbeat cycle")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat cycle: {e}")
                await asyncio.sleep(5)
    
    async def simulate_charging_cycle(self):
        """Simulate random charging events"""
        while True:
            try:
                # Wait a random time before simulating a new event
                await asyncio.sleep(random.randint(30, 60))
                
                # Only simulate new transactions if not already in one
                if not self.transaction_id:
                    await self.simulate_transaction_start(random.choice(self.authorized_tags))
            except websockets.exceptions.ConnectionClosed:
                logger.info("Connection closed, stopping simulation cycle")
                break
            except Exception as e:
                logger.error(f"Error in simulation cycle: {e}")
                await asyncio.sleep(5)
    
    async def simulate_transaction_start(self, id_tag):
        """Simulate a charging transaction start"""
        # Send status notification - preparing
        await self.send_status_notification("Preparing")
        await asyncio.sleep(1)
        
        # Authorize the card
        await self.send_authorize(id_tag)
        await asyncio.sleep(1)
        
        # Start the transaction
        await self.send_start_transaction(id_tag)
        
        # Transaction ID will be set when we get the response
        # For now, we'll wait a bit to make sure we've received the response
        await asyncio.sleep(2)
        
        if self.transaction_id:
            # Change status to charging
            await self.send_status_notification("Charging")
            
            # Simulate meter values during charging
            for _ in range(3):
                await asyncio.sleep(10)
                await self.send_meter_values()
            
            # End transaction after a while, if it hasn't been ended by a remote command
            if self.transaction_id:
                await asyncio.sleep(random.randint(20, 40))
                await self.simulate_transaction_stop()
    
    async def simulate_transaction_stop(self):
        """Simulate a charging transaction stop"""
        if not self.transaction_id:
            return
        
        # Send status notification - finishing
        await self.send_status_notification("Finishing")
        await asyncio.sleep(1)
        
        # Stop the transaction
        meter_stop = random.randint(20000, 30000)
        await self.send_stop_transaction(meter_stop)
        
        # Back to available
        await asyncio.sleep(2)
        await self.send_status_notification("Available")

async def main():
    # Configuration parameters
    cp_id = "TEST_CHARGER_001"  # Charge point ID
    server_url = "ws://localhost:9000/ocpp"  # OCPP server URL
    
    # Create and connect the charge point
    cp = ChargePoint(cp_id, server_url)
    await cp.connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in main: {e}")