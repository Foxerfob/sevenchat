import asyncio
import logging
import os
import sys
from dotenv import load_dotenv, dotenv_values 
from ui import BaseUserInterface, ConsoleInterface
from nio import (
    AsyncClient, 
    AsyncClientConfig,
    MatrixRoom, 
    RoomMessageText, 
    InviteMemberEvent, 
    MegolmEvent
)

#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class BotCallbacks:
    def __init__(self, client: AsyncClient, ui: BaseUserInterface):
        self.client = client
        self.ui = ui


    async def on_message(self, room: MatrixRoom, event: RoomMessageText):
        self.ui.on_message(room, event)


    async def on_decrypted_event(self, room: MatrixRoom, event: MegolmEvent):
       if isinstance(event, RoomMessageText):
            await self.on_message(room, event)


    async def send_text(self, room_id: str, text: str):
        await self.client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": text}
        )


class MatrixBot:
    def __init__(self, homeserver: str, user_id: str, password: str, device_id: str, store_path: str, ui: BaseUserInterface):
        self.ui = ui
        self.ui.bot = self
        self.homeserver = homeserver
        self.user_id = user_id
        self.password = password
        self.device_id = device_id

        client_config = AsyncClientConfig(encryption_enabled=True)
        self.client = AsyncClient(
            homeserver, 
            user_id, 
            device_id=device_id, 
            store_path=store_path,
            config=client_config
        )
        
        self.callbacks = BotCallbacks(self.client, self.ui)
        self._register_callbacks()


    def _register_callbacks(self):
        self.client.add_event_callback(self.callbacks.on_message, RoomMessageText)
        self.client.add_event_callback(self.callbacks.on_decrypted_event, MegolmEvent)


    def _trust_all_devices(self) -> None:
        for u_id, devices in self.client.device_store.items():
            for d_id, device in devices.items():
                if not device.verified and not device.blacklisted:
                    self.client.verify_device(device)


    async def login(self) -> bool:
        self.ui.log_info(f"Connection to {self.homeserver}...")
        response = await self.client.login(self.password)
       
        if type(response).__name__ == "LoginError":
            self.ui.log_info(f"LoginError: {response.message}")
            return False

        self.client.load_store()
        self._trust_all_devices()
            
        self.ui.log_info("Successful login.")
        return True

    async def start_sync(self):
        await self.client.sync_forever(timeout=30000, full_state=True)


    async def close(self):
        await self.client.close()
        self.ui.log_info("Connection closed")


async def main():
    load_dotenv()

    HOMESERVER = os.getenv("HOMESERVER")
    USER_ID = os.getenv("USER_ID")
    PASSWORD = os.getenv("PASSWORD") 
    DEVICE_ID = os.getenv("DEVICE_ID") 
    STORE_PATH = os.getenv("STORE_PATH")

    os.makedirs(STORE_PATH, exist_ok=True)

    ui = ConsoleInterface()
    bot = MatrixBot(HOMESERVER, USER_ID, PASSWORD, DEVICE_ID, STORE_PATH, ui)

    if not await bot.login():
        return

    main_loop = asyncio.gather(
            bot.start_sync(),
            ui.run()
        )

    try:
        await main_loop
    except EOFError:
        self.ui.log_info("User inrerrupt...")
    finally:
        await bot.close()
        main_loop.cancel()
        raise EOFError

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except EOFError:
        pass
