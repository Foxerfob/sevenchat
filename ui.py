import asyncio
import os
from abc import ABC, abstractmethod

class BaseUserInterface(ABC):
    """Абстрактный класс интерфейса. Сюда добавляем методы вывода данных юзеру."""

    @abstractmethod
    async def run(self, bot):
        pass


    @abstractmethod
    def on_message(self, room, event):
        pass


    @abstractmethod
    def log_info(self, message: str):
        pass


class ConsoleInterface(BaseUserInterface):
    """Простейшая реализация для терминала."""

    def __init__(self):
        self.events = dict()
        self.current_room = None


    async def run(self):
        """Реализация цикла для консоли.""" 
        self.log_info("Type /help to list of commands.")

        if not hasattr(self, 'bot'):
            raise ValueError("ConsoleInterface.bot was not set before calling ConsoleInterface.run()")

        while True:
            # Читаем ввод, не блокируя основной поток

            text = await asyncio.to_thread(input, "")
            text = text.strip()

            if text:
                if text[0] == "/":
                    self.handle_command(text) 
                else:
                    if self.current_room:
                        await self.bot.callbacks.send_text(self.current_room.room_id, text)


    def handle_command(self,  command: str):
        args = command[1:].split()
        if len(args) >= 1:
            match args[0]:
                case "help":
                    if len(args) >= 2:
                        match args[1]:
                            case "help":
                                print("""help - list of commands.
       <command> - help for the selected command.""")
                            case "room":
                                print("""room - room actions.
       list - list of rooms.
       <room number> - open selected room.""")
                            case "exit":
                                print("exit - exit.")
                            case _:
                                print(f"Unknown command {args[1]}")
                    else:
                        self.handle_command("/help help")
                        self.handle_command("/help room")
                        self.handle_command("/help exit")

                case "room":
                    if len(args) >= 2:
                        match args[1]:
                            case "list":
                                all_rooms = self.bot.client.rooms
                                for i, item in enumerate(all_rooms.items()):
                                    print(f"{i}: {item[1].display_name}")
                            case _:
                                try:
                                    room_number = int(args[1])
                                except ValueError:
                                    self.handle_command("/help room")
                                    return

                                try:
                                    all_rooms = self.bot.client.rooms
                                    item = tuple(all_rooms.items())[room_number]
                                    self.current_room = item[1]

                                    os.system('clear')
                                    print(f"[{self.current_room.display_name}]")
                                    for event in self.events[self.current_room]:
                                        print(f"{event.sender}: {event.body}")
                                except IndexError:
                                    print("Incorrect room number.")
                    else:
                        self.handle_command("/help room")
                case "exit":
                    raise EOFError
                case _:
                    print(f"Unknown command {args[0]}\nType /help to list of commands")


    def on_message(self, room, event):
        self.events[room] = self.events.get(room, [])
        self.events[room].append(event)
        if room == self.current_room:
            print(f"{event.sender}: {event.body}")


    def log_info(self, message: str):
        print(f"[INFO]: {message}")
