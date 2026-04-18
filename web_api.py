import asyncio
from flask import Flask, request, jsonify
from ui import BaseUserInterface

class WebAPIInterface(BaseUserInterface):
    """Web-API интерфейс на базе Flask для управления Matrix-ботом."""

    def __init__(self, host="127.0.0.1", port=7000):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.events = {}  # Словарь: room_id -> список сообщений
        self.loop = None  # Ссылка на event loop для потокобезопасных вызовов

        self._setup_routes()

    def _setup_routes(self):
        """Инициализация маршрутов Flask."""
        
        @self.app.route("/api/rooms", methods=["GET"])
        def get_rooms(): 
            rooms_data = []
            for room_id, room in self.bot.client.rooms.items():
                rooms_data.append({
                    "room_id": room_id,
                    "name": room.display_name,
                    "member_count": room.member_count
                })
            return jsonify({"rooms": rooms_data}), 200

        @self.app.route("/api/rooms/<room_id>/messages", methods=["GET"])
        def get_messages(room_id):
            room = self.bot.client.rooms.get(room_id)
            if not room:
                return jsonify({"error": "Room not found"}), 404
            
            # Возвращаем историю, которую успел собрать интерфейс
            messages = self.events.get(room_id, [])
            return jsonify({
                "room_id": room_id,
                "room_name": room.display_name,
                "messages": messages
            }), 200

        @self.app.route("/api/rooms/<room_id>/send", methods=["POST"])
        def send_message(room_id):
            data = request.get_json()
            if not data or "text" not in data:
                return jsonify({"error": "Missing 'text' field in JSON body"}), 400

            text = data["text"]
            
            # Flask работает в отдельном потоке, поэтому пробрасываем 
            # корутину отправки сообщения в основной event loop
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.bot.callbacks.send_text(room_id, text),
                    self.loop
                )
                return jsonify({"status": "Message queued for sending"}), 202
            else:
                return jsonify({"error": "Event loop is not running"}), 500

    async def run(self):
        """Запуск Flask сервера в отдельном потоке."""
        if not hasattr(self, 'bot'):
            raise ValueError("WebAPIInterface.bot was not set before calling run()")

        # Сохраняем текущий асинхронный цикл, чтобы Flask мог кидать в него задачи
        self.loop = asyncio.get_running_loop()
        
        self.log_info(f"Starting Flask Web-API on http://{self.host}:{self.port}")
        
        # Запускаем блокирующий Flask в пуле потоков
        await asyncio.to_thread(
            self.app.run, 
            host=self.host, 
            port=self.port, 
            use_reloader=False, # reloader конфликтует с asyncio
            debug=False
        )

    def on_message(self, room, event):
        """Обработка новых сообщений и сохранение их в памяти для API."""
        room_id = room.room_id
        if room_id not in self.events:
            self.events[room_id] = []
        
        # Сохраняем только сериализуемые данные, чтобы Flask мог отдать их в JSON
        message_data = {
            "sender": event.sender,
            "body": event.body,
            "timestamp": event.server_timestamp
        }
        
        self.events[room_id].append(message_data)
        self.log_info(f"Stored new message in API cache for {room.display_name}")

    def log_info(self, message: str):
        print(f"[INFO]: {message}")
