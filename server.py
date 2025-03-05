import asyncio
import websockets
import logging
from datetime import datetime, timezone
from ocpp.routing import on
from ocpp.v16 import ChargePoint, call_result
from ocpp.v16.enums import RegistrationStatus

# Enable logging for insight into the server's operation
logging.basicConfig(level=logging.INFO)

class MyChargePoint(ChargePoint):

    @on('BootNotification')
    async def on_boot_notification(self, charge_point_model, charge_point_vendor):
        logging.info(f"Handler triggered: BootNotification received from {self.id}")
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        logging.info(
        f"BootNotification details - Model: {charge_point_model}, Vendor: {charge_point_vendor}"
        )
        return call_result.BootNotification(
        current_time=now,
        interval=10,
        status=RegistrationStatus.accepted
        )
    
    @on('Heartbeat')
    async def on_heartbeat(self):
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        logging.info(f"Heartbeat received from {self.id}")
        return call_result.Heartbeat(current_time=now)

async def on_connect(websocket, path):

    """
    Called for every new charge point connection.
    The charge point's ID is expected to be part of the URL (e.g., ws://localhost:9000/CP_123).
    """

    charge_point_id = path.strip('/')
    cp = MyChargePoint(charge_point_id, websocket)
    await cp.start()

async def main():

    # Start the WebSocket server on localhost port 9000.
    async with websockets.serve(on_connect, 'localhost', 9000):
        logging.info("OCPP server is running on ws://localhost:9000")
        await asyncio.Future()  # Run forever

if __name__ == '__main__':

    asyncio.run(main())
