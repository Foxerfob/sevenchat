import asyncio
import os
from flask import Flask, request, jsonify, render_template
from ui import BaseUserInterface

class WebAPIInterface(BaseUserInterface):
    def __init__(self, host="127.0.0.1", port=7000):
        self.host = host
        self.port = port
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.app = Flask(
            __name__, 
            template_folder=os.path.join(base_dir, 'templates'),
            static_folder=os.path.join(base_dir, 'static')
        )
        self.events = {}  
        self.loop = None
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

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

        @self.app.route("/api/rooms/<room_id>/history", methods=["GET"])
        def get_room_history(room_id):
            start_token = request.args.get("start_from")
            if not self.loop: return jsonify({"error": "Loop error"}), 500

            async def _fetch():
                token = start_token if start_token else getattr(self.bot.client.rooms[room_id], 'prev_batch', None)
                response = await self.bot.client.room_messages(room_id, start=token, limit=30)
                
                history = []
                for event in response.chunk:
                    if hasattr(event, 'body'):
                        history.append({
                            "event_id": event.event_id,
                            "sender": event.sender,
                            "body": event.body,
                            "timestamp": event.server_timestamp
                        })
                history.reverse() 
                return {"messages": history, "next_start": response.end}

            future = asyncio.run_coroutine_threadsafe(_fetch(), self.loop)
            try:
                return jsonify(future.result(timeout=10)), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/rooms/<room_id>/sync", methods=["GET"])
        def sync_new_messages(room_id):
            new_msgs = self.events.get(room_id, [])
            self.events[room_id] = [] 
            return jsonify({"messages": new_msgs}), 200

        @self.app.route("/api/rooms/<room_id>/send", methods=["POST"])
        def send_message(room_id):
            data = request.get_json()
            if not data or "text" not in data:
                return jsonify({"error": "Missing 'text' field"}), 400
            
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.bot.callbacks.send_text(room_id, data["text"]),
                    self.loop
                )
                return jsonify({"status": "Message queued"}), 202
            return jsonify({"error": "Loop error"}), 500

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.log_info(f"Starting Flask Web-API on http://{self.host}:{self.port}")
        
        await asyncio.to_thread(
            self.app.run, 
            host=self.host, 
            port=self.port, 
            use_reloader=False, 
            debug=False
        )

    def on_message(self, room, event):
        room_id = room.room_id
        if room_id not in self.events:
            self.events[room_id] = []
        
        self.events[room_id].append({
            "event_id": event.event_id,
            "sender": event.sender,
            "body": event.body,
            "timestamp": event.server_timestamp
        })

    def log_info(self, message: str):
        print(f"[INFO]: {message}")
