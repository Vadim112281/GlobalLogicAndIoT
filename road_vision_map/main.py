import asyncio
import json
import threading
import tkinter as tk
import tkinter.simpledialog as sd
import tkintermapview
import os
import urllib.error
import urllib.request
from datetime import datetime

import websockets

# Store API endpoints (used by UI)
STORE_HTTP_BASE = os.environ.get("STORE_HTTP_BASE", "http://127.0.0.1:8000")
STORE_WS_URL = os.environ.get("STORE_WS_URL", "ws://127.0.0.1:8000/ws/")


class MapViewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Road Vision - Аналітична Карта")
        self.geometry("1000x700")

        # UI state
        self.total_budget: float = 0.0
        self.markers_by_id: dict[int, object] = {}
        self.cost_by_id: dict[int, float] = {}

        # Map widget
        self.map_widget = tkintermapview.TkinterMapView(
            self, width=1000, height=700, corner_radius=0
        )
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_position(50.4501, 30.5234)  # Київ
        self.map_widget.set_zoom(13)

        # Add manual pothole via right click
        self.map_widget.add_right_click_menu_command(
            label="Додати яму тут",
            command=self.add_manual_marker,
            pass_coords=True,
        )

        # Budget panel
        self.label_budget = tk.Label(
            self,
            text="Загальний бюджет: 0 грн",
            font=("Arial", 14, "bold"),
            fg="darkblue",
            bg="white",
        )
        self.label_budget.place(x=10, y=10)

        self.clear_button = tk.Button(
            self,
            text="Очистити карту",
            command=self.clear_all_markers,
            bg="red",
            fg="white",
        )
        self.clear_button.place(x=10, y=50)

        # Start Store live sync
        threading.Thread(target=self.ws_listener, daemon=True).start()
        threading.Thread(target=self.fetch_and_render_existing, daemon=True).start()

    def calculate_repair_cost(self, length: float, width: float, depth: float) -> float:
        """Fallback pricing formula (Store is the source of truth)."""
        volume = length * width * depth
        base_service = 1500.0
        material_price = 0.8
        difficulty = 1.5 if depth > 5 else 1.0
        cost = (base_service + (volume * material_price)) * difficulty
        return round(cost, 2)

    def _update_budget_label(self):
        self.label_budget.config(text=f"Загальний бюджет: {round(self.total_budget, 2)} грн")

    # -------------------------
    # Store HTTP helpers
    # -------------------------
    def http_get_json(self, path: str):
        url = f"{STORE_HTTP_BASE}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None

    def http_post_json(self, path: str, payload):
        url = f"{STORE_HTTP_BASE}{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None

    def http_delete(self, path: str):
        url = f"{STORE_HTTP_BASE}{path}"
        req = urllib.request.Request(url, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                _ = resp.read()
        except Exception:
            # UI will be corrected by websocket events
            pass

    # -------------------------
    # WebSocket live sync
    # -------------------------
    def ws_listener(self):
        async def listen_forever():
            while True:
                try:
                    async with websockets.connect(STORE_WS_URL) as ws:
                        while True:
                            raw = await ws.recv()
                            try:
                                message = json.loads(raw)
                            except Exception:
                                continue
                            self.after(0, self.handle_ws_message, message)
                except Exception:
                    await asyncio.sleep(2)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(listen_forever())

    def handle_ws_message(self, message: dict):
        msg_type = message.get("type")
        if msg_type == "created":
            for item in message.get("items") or []:
                self.add_or_update_marker_from_store_item(item)
        elif msg_type == "updated":
            item = message.get("item")
            if item:
                self.add_or_update_marker_from_store_item(item)
        elif msg_type == "deleted":
            item_id = message.get("id")
            if item_id is not None:
                self.remove_marker_by_id(item_id)

    # -------------------------
    # Marker + budget logic
    # -------------------------
    def add_or_update_marker_from_store_item(self, item: dict):
        item_id = int(item["id"])
        lat = float(item["latitude"])
        lon = float(item["longitude"])
        road_state = item.get("road_state", "unknown")

        dims = item.get("dimensions") or {}
        length = float(dims.get("length", 20))
        width = float(dims.get("width", 20))
        depth = float(dims.get("depth", 3))

        cost = item.get("cost")
        if cost is None:
            cost = self.calculate_repair_cost(length, width, depth)
        cost = float(cost)

        # Budget delta (avoid double count on create vs re-sync)
        if item_id in self.cost_by_id:
            self.total_budget += cost - self.cost_by_id[item_id]
        else:
            self.total_budget += cost
        self.cost_by_id[item_id] = cost
        self._update_budget_label()

        color = "red" if depth > 5 else "orange"
        marker_text = f"Стан: {road_state}\nРозмір: {length}x{width}x{depth}см\nЦіна: {cost} грн"

        # Replace marker to keep text/color consistent
        if item_id in self.markers_by_id:
            try:
                self.markers_by_id[item_id].delete()
            except Exception:
                pass

        self.markers_by_id[item_id] = self.map_widget.set_marker(
            lat,
            lon,
            text=marker_text,
            marker_color_outside=color,
            command=lambda marker, mid=item_id: self.request_delete(mid),
        )

    def remove_marker_by_id(self, item_id: int):
        item_id = int(item_id)
        if item_id in self.markers_by_id:
            try:
                self.markers_by_id[item_id].delete()
            except Exception:
                pass
            del self.markers_by_id[item_id]

        if item_id in self.cost_by_id:
            self.total_budget -= float(self.cost_by_id[item_id])
            del self.cost_by_id[item_id]
            self._update_budget_label()

    def request_delete(self, item_id: int):
        threading.Thread(
            target=self.http_delete,
            args=(f"/processed_agent_data/{item_id}",),
            daemon=True,
        ).start()

    def fetch_and_render_existing(self):
        try:
            items = self.http_get_json("/processed_agent_data/")
        except Exception:
            return
        if not isinstance(items, list):
            return
        for item in items:
            self.after(0, self.add_or_update_marker_from_store_item, item)

    def clear_all_markers(self):
        # Clear UI state
        self.map_widget.delete_all_marker()
        self.markers_by_id.clear()
        self.cost_by_id.clear()
        self.total_budget = 0.0
        self._update_budget_label()
        # Re-sync from Store
        threading.Thread(target=self.fetch_and_render_existing, daemon=True).start()

    # -------------------------
    # Manual add
    # -------------------------
    def add_manual_marker(self, coords):
        lat, lon = coords

        road_state = sd.askstring("Ввід", "Який стан дороги? (напр. Вибоїна):")
        if not road_state:
            return

        length = sd.askfloat("Ввід", "Довжина (см):", minvalue=1.0)
        width = sd.askfloat("Ввід", "Ширина (см):", minvalue=1.0)
        depth = sd.askfloat("Ввід", "Глибина (см):", minvalue=1.0)

        if not all(v is not None for v in [length, width, depth]):
            return

        dimensions = {
            "length": float(length),
            "width": float(width),
            "depth": float(depth),
        }

        # Payload expected by Store:
        # ProcessedAgentData = { road_state, agent_data, dimensions }
        # agent_data.accelerometer.x/y are not used for pricing; we set them to 0.
        payload = [
            {
                "road_state": road_state,
                "agent_data": {
                    "accelerometer": {"x": 0.0, "y": 0.0, "z": float(depth)},
                    "gps": {"latitude": float(lat), "longitude": float(lon)},
                    "timestamp": datetime.now().isoformat(),
                },
                "dimensions": dimensions,
            }
        ]

        def worker():
            try:
                self.http_post_json("/processed_agent_data/", payload)
            except Exception:
                return
            # Optional fallback: if WS is delayed, re-sync from Store.
            threading.Thread(target=self.fetch_and_render_existing, daemon=True).start()

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = MapViewApp()
    app.mainloop()