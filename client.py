import asyncio
import logging
import websockets
from datetime import datetime, timezone

from ocpp.v16 import ChargePoint, call

logging.basicConfig(level=logging.INFO)

class ChargePointClient(ChargePoint):

    async def send_boot_notification(self):
        logging.info("Sending BootNotification...")
        request = call.BootNotification(
            charge_point_model='SingleSocketCharger',
            charge_point_vendor='MyVendor'
        )
        response = await self.call(request)
        logging.info("BootNotification response: %s", response)

    async def send_heartbeats(self):
        logging.info("Heartbeat task started")
        while True:
            try:
                logging.info("Sending heartbeat...")
                response = await self.call(call.Heartbeat())
                logging.info("Heartbeat response: %s", response)
                await asyncio.sleep(5)
            except Exception as e:
                logging.error("Error sending heartbeat: %s", e)
                break

async def main():
    async with websockets.connect('ws://localhost:9000/CP_123') as ws:
        cp_client = ChargePointClient("CP_123", ws)
        # Start the message loop concurrently so that incoming responses can be processed.
        start_task = asyncio.create_task(cp_client.start())
        # Now send the BootNotification; its response will be handled by the already running message loop.
        await cp_client.send_boot_notification()
        # Start the heartbeat task concurrently.
        heartbeat_task = asyncio.create_task(cp_client.send_heartbeats())
        await asyncio.gather(start_task, heartbeat_task)

if __name__ == '__main__':
    asyncio.run(main())
