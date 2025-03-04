import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def handle_connection(websocket, path=None):
    try:
        # Log when a client connects
        logger.info(f"Client connected from {websocket.remote_address}")
        
        # Receive messages from the client
        async for message in websocket:
            try:
                # Parse the incoming message
                data = json.loads(message)
                logger.info(f"Received message: {data}")
                
                # Basic response (you'd typically implement OCPP-specific logic here)
                response = {
                    "status": "Accepted"
                }
                
                # Send response back to client
                await websocket.send(json.dumps(response))
            
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {message}")
    
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")

async def start_server():
    # Start WebSocket server
    server = await websockets.serve(
        handle_connection, 
        "localhost", 
        9000
    )
    
    logger.info("OCPP Server started on ws://localhost:9000")
    
    # Keep the server running
    await server.wait_closed()

# Run the server
if __name__ == "__main__":
    asyncio.run(start_server())