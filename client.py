import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def connect_to_server():
    try:
        # Establish WebSocket connection
        async with websockets.connect(
            "ws://localhost:9000", 
            subprotocols=['ocpp1.6']
        ) as websocket:
            logger.info("Connected to OCPP server")
            
            # Send an initial OCPP-like message
            initial_message = {
                "action": "Authorize",
                "id": "test-client-1",
                "payload": {
                    "idTag": "test-tag-123"
                }
            }
            
            # Send the message
            await websocket.send(json.dumps(initial_message))
            logger.info("Sent initial message")
            
            # Wait for and log server response
            response = await websocket.recv()
            logger.info(f"Server response: {response}")
            
            # Keep the connection open and listen for messages
            while True:
                try:
                    message = await websocket.recv()
                    logger.info(f"Received: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Connection closed by server")
                    break
    
    except Exception as e:
        logger.error(f"Connection error: {e}")

# Run the client
if __name__ == "__main__":
    asyncio.run(connect_to_server())