import asyncio
import json
import threading
import tkinter as tk
import tkinter.messagebox as mb
import tkinter.simpledialog as sd
from datetime import datetime
from urllib import error, request

import tkintermapview
import websockets


STORE_API_URL = "http://127.0.0.1:8000/processed_agent_data/"
WEBSOCKET_URL = "ws://127.0.0.1:8000/ws/"


def http_json(url, method="GET", payload=None):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None


class MapViewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Road Vision - Аналітична Карта")
        self.geometry("1000x700")

        self.markers = {}
        self.items = {}
        self.add_marker_mode = False

        self.map_widget = tkintermapview.TkinterMapView(
            self, width=1000, height=700, corner_radius=0
        )
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_position(50.4501, 30.5234)
        self.map_widget.set_zoom(13)
        self.map_widget.add_left_click_map_command(self.on_map_left_click)

        self.map_widget.add_right_click_menu_command(
            label="Додати яму тут",
            command=self.add_manual_marker,
            pass_coords=True,
        )

        panel_bg = "#1f2937"
        panel_fg = "#f9fafb"
        self.control_panel = tk.Frame(
            self,
            bg=panel_bg,
            highlightbackground="#111827",
            highlightthickness=1,
            bd=0,
        )
        self.control_panel.place(x=10, y=10, width=310)

        self.label_budget = tk.Label(
            self.control_panel,
            text="Загальний бюджет: 0 грн",
            font=("Arial", 14, "bold"),
            fg=panel_fg,
            bg=panel_bg,
            anchor="w",
            justify="left",
            wraplength=280,
        )
        self.label_budget.pack(fill="x", padx=12, pady=(12, 8))

        self.add_button = tk.Button(
            self.control_panel,
            text="Додати яму",
            command=self.enable_add_marker_mode,
            bg="#2563eb",
            fg="#111827",
            activebackground="#1d4ed8",
            activeforeground="#111827",
            relief="flat",
            padx=12,
            pady=8,
            borderwidth=0,
            font=("Arial", 12, "bold"),
        )
        self.add_button.pack(fill="x", padx=12, pady=(0, 8))

        self.clear_button = tk.Button(
            self.control_panel,
            text="Очистити карту",
            command=self.clear_all_markers,
            bg="#dc2626",
            fg="#111827",
            activebackground="#b91c1c",
            activeforeground="#111827",
            relief="flat",
            padx=12,
            pady=8,
            borderwidth=0,
            font=("Arial", 12, "bold"),
        )
        self.clear_button.pack(fill="x", padx=12, pady=(0, 8))

        self.label_hint = tk.Label(
            self.control_panel,
            text="",
            font=("Arial", 11),
            fg="#86efac",
            bg=panel_bg,
            anchor="w",
            justify="left",
            wraplength=280,
        )
        self.label_hint.pack(fill="x", padx=12, pady=(0, 12))

    def clear_all_markers(self):
        for marker in self.markers.values():
            marker.delete()
        self.markers.clear()
        self.items.clear()
        self.refresh_budget()

    def refresh_budget(self):
        total = sum((item.get("repair_cost") or 0) for item in self.items.values())
        self.label_budget.config(text=f"Загальний бюджет: {round(total, 2)} грн")

    def set_hint(self, text):
        self.label_hint.config(text=text)

    def enable_add_marker_mode(self):
        self.add_marker_mode = True
        self.set_hint("Режим додавання увімкнено: клікни лівою кнопкою по карті")

    def disable_add_marker_mode(self):
        self.add_marker_mode = False
        self.set_hint("")

    def on_map_left_click(self, coords):
        if not self.add_marker_mode:
            return

        self.disable_add_marker_mode()
        self.add_manual_marker(coords)

    def marker_color(self, item):
        road_state = (item.get("road_state") or "").strip().lower()
        depth = item.get("depth") or 0

        if road_state == "normal":
            return "green"
        if item.get("repair_cost") is not None:
            return "red" if depth > 5 else "orange"
        return "red"

    def marker_text(self, item):
        lines = [f"Стан: {item.get('road_state', 'Невідомо')}"]

        source = item.get("source", "sensor")
        lines.append(f"Джерело: {'Ручне' if source == 'manual' else 'Авто'}")

        length = item.get("length")
        width = item.get("width")
        depth = item.get("depth")
        if None not in (length, width, depth):
            lines.append(f"Розмір: {length}x{width}x{depth}см")

        repair_cost = item.get("repair_cost")
        if repair_cost is not None:
            lines.append(f"Ціна: {repair_cost} грн")

        timestamp = item.get("timestamp")
        if timestamp:
            lines.append(f"Час: {timestamp}")

        return "\n".join(lines)

    def upsert_item(self, item):
        item_id = item.get("id")
        lat = item.get("latitude")
        lon = item.get("longitude")

        if item_id is None or lat is None or lon is None:
            return

        old_marker = self.markers.pop(item_id, None)
        if old_marker is not None:
            old_marker.delete()

        self.items[item_id] = item
        self.markers[item_id] = self.map_widget.set_marker(
            lat,
            lon,
            text=self.marker_text(item),
            marker_color_outside=self.marker_color(item),
        )
        self.refresh_budget()

    def remove_item(self, item_id):
        marker = self.markers.pop(item_id, None)
        if marker is not None:
            marker.delete()
        self.items.pop(item_id, None)
        self.refresh_budget()

    def load_existing_data(self):
        try:
            items = http_json(STORE_API_URL)
            for item in items or []:
                self.upsert_item(item)
        except error.URLError as exc:
            mb.showwarning(
                "Store недоступний",
                f"Не вдалося завантажити дані зі Store: {exc}",
            )

    def add_manual_marker(self, coords):
        lat, lon = coords

        road_state = sd.askstring("Ввід", "Який стан дороги? (напр. Вибоїна):")
        if not road_state:
            self.set_hint("Додавання скасовано")
            return

        length = sd.askfloat("Ввід", "Довжина (см):", minvalue=1.0)
        width = sd.askfloat("Ввід", "Ширина (см):", minvalue=1.0)
        depth = sd.askfloat("Ввід", "Глибина (см):", minvalue=1.0)

        if not all(value is not None for value in [length, width, depth]):
            self.set_hint("Додавання скасовано")
            return

        payload = [
            {
                "road_state": road_state,
                "source": "manual",
                "dimensions": {
                    "length": length,
                    "width": width,
                    "depth": depth,
                },
                "agent_data": {
                    "gps": {"latitude": lat, "longitude": lon},
                    "timestamp": datetime.now().isoformat(),
                },
            }
        ]

        try:
            created_items = http_json(STORE_API_URL, method="POST", payload=payload)
            for item in created_items or []:
                self.upsert_item(item)
            self.set_hint("Яму успішно додано")
        except error.URLError as exc:
            self.set_hint("Не вдалося додати яму")
            mb.showerror(
                "Помилка збереження",
                f"Не вдалося зберегти яму у Store: {exc}",
            )


async def websocket_listener(app):
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                while True:
                    raw_message = await websocket.recv()
                    payload = json.loads(raw_message)
                    event_type = payload.get("type")

                    if event_type == "created":
                        for item in payload.get("items", []):
                            app.after(0, app.upsert_item, item)
                    elif event_type == "updated":
                        item = payload.get("item")
                        if item:
                            app.after(0, app.upsert_item, item)
                    elif event_type == "deleted":
                        item_id = payload.get("id")
                        if item_id is not None:
                            app.after(0, app.remove_item, item_id)
        except Exception:
            await asyncio.sleep(3)


def start_websocket_thread(app):
    def runner():
        asyncio.run(websocket_listener(app))

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


if __name__ == "__main__":
    app = MapViewApp()
    app.load_existing_data()
    start_websocket_thread(app)
    app.mainloop()