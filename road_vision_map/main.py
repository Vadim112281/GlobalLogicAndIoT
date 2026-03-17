import tkinter as tk
import tkintermapview
import json
import asyncio
import websockets
import threading
import paho.mqtt.client as mqtt
import tkinter.simpledialog as sd  # Виправляє помилку з sd

# Налаштування
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "agent_data_topic"
WEBSOCKET_URL = "ws://127.0.0.1:8000/ws/"

class MapViewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Road Vision - Аналітична Карта")
        self.geometry("1000x700")

        # Віджет карти
        self.map_widget = tkintermapview.TkinterMapView(self, width=1000, height=700, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_position(50.4501, 30.5234) # Київ
        self.map_widget.set_zoom(13)

        # Реєстрація меню для додавання ям вручну
        self.map_widget.add_right_click_menu_command(
            label="Додати яму тут",
            command=self.add_manual_marker,
            pass_coords=True
        )

        # Аналітична панель
        self.total_budget = 0
        self.label_budget = tk.Label(self, text="Загальний бюджет: 0 грн", font=("Arial", 14, "bold"), fg="darkblue", bg="white")
        self.label_budget.place(x=10, y=10)

        self.clear_button = tk.Button(self, text="Очистити карту", command=self.clear_all_markers, bg="red", fg="white")
        self.clear_button.place(x=10, y=50)

    def calculate_repair_cost(self, length, width, depth):
        """Економічна формула розрахунку вартості."""
        volume = length * width * depth
        base_service = 1500 
        material_price = 0.8 
        difficulty = 1.5 if depth > 5 else 1.0
        cost = (base_service + (volume * material_price)) * difficulty
        return round(cost, 2)

    def add_marker(self, lat, lon, road_state, dimensions):
        """Додає маркер з ціною ремонту."""
        length = dimensions.get("length", 20)
        width = dimensions.get("width", 20)
        depth = dimensions.get("depth", 3)

        cost = self.calculate_repair_cost(length, width, depth)
        self.total_budget += cost
        self.label_budget.config(text=f"Загальний бюджет: {round(self.total_budget, 2)} грн")

        color = "red" if depth > 5 else "orange"
        marker_text = f"Стан: {road_state}\nРозмір: {length}x{width}x{depth}см\nЦіна: {cost} грн"
        
        self.map_widget.set_marker(
            lat, lon, 
            text=marker_text, 
            marker_color_outside=color,
            command=lambda marker: marker.delete() # Видалення при кліку
        )

    def add_manual_marker(self, coords):
        """Створює маркер через клік правою кнопкою миші."""
        lat, lon = coords
        
        road_state = sd.askstring("Ввід", "Який стан дороги? (напр. Вибоїна):")
        if not road_state: return
        
        length = sd.askfloat("Ввід", "Довжина (см):", minvalue=1.0)
        width = sd.askfloat("Ввід", "Ширина (см):", minvalue=1.0)
        depth = sd.askfloat("Ввід", "Глибина (см):", minvalue=1.0)
        
        if all(v is not None for v in [length, width, depth]):
            dimensions = {"length": length, "width": width, "depth": depth}
            self.add_marker(lat, lon, road_state, dimensions)
            # Відправляємо в MQTT, щоб синхронізувати з іншими
            send_to_mqtt(lat, lon, road_state, dimensions)

    def clear_all_markers(self):
        self.map_widget.delete_all_marker()
        self.total_budget = 0
        self.label_budget.config(text="Загальний бюджет: 0 грн")

# --- Мережева логіка ---

def send_to_mqtt(lat, lon, road_state, dimensions):
    payload = {
        "gps": {"latitude": lat, "longitude": lon},
        "road_state": road_state,
        "dimensions": dimensions
    }
    mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))

def on_mqtt_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        gps = data.get("gps", {})
        dimensions = data.get("dimensions", {"length": 20, "width": 20, "depth": 3})
        app.after(0, app.add_marker, gps["latitude"], gps["longitude"], data.get("road_state", "Яма"), dimensions)
    except: pass

if __name__ == "__main__":
    app = MapViewApp()

    # MQTT
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_message = on_mqtt_message
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        mqtt_client.subscribe(MQTT_TOPIC)
        mqtt_client.loop_start()
    except: print("MQTT не підключено")

    app.mainloop()