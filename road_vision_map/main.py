import tkinter as tk
import tkintermapview
import asyncio
import websockets
import json
import threading

# URL твого Store
WEBSOCKET_URL = "ws://127.0.0.1:8000/ws/"

class MapViewApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Road Vision - MapUI")
        self.geometry("800x600")

        # Віджет карти
        self.map_widget = tkintermapview.TkinterMapView(self, width=800, height=600, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        
        # Центруємо карту (координати за замовчуванням)
        self.map_widget.set_position(50.4501, 30.5234) # Київ
        self.map_widget.set_zoom(13)

    def add_marker(self, lat, lon, road_state):
        """Додає маркер на карту. Колір залежить від стану."""
        # Якщо в стані дороги є слова "pit", "ям" тощо - маркер червоний, інакше зелений
        is_bad_road = any(word in road_state.lower() for word in ["pit", "ям", "crack", "вибоїн"])
        color = "red" if is_bad_road else "green"
        
        self.map_widget.set_marker(
            lat, lon, 
            text=f"Стан: {road_state}", 
            marker_color_outside=color,
            marker_color_circle=color
        )

async def listen_to_store(app):
    """Слухає WebSocket зі Store та передає координати на UI."""
    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            print("Підключено до Store WebSocket!")
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                # Обробляємо повідомлення про створення нових записів (з вашого бекенду)
                if data.get("type") == "created":
                    for item in data.get("items", []):
                        lat = item.get("latitude")
                        lon = item.get("longitude")
                        road_state = item.get("road_state", "Unknown")
                        
                        if lat is not None and lon is not None:
                            # Оновлюємо UI з головного потоку Tkinter
                            app.after(0, app.add_marker, lat, lon, road_state)
                            
    except Exception as e:
        print(f"Помилка підключення до WebSocket: {e}")

def start_async_loop(app):
    """Фоновий потік для асинхронного WebSocket."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_to_store(app))

if __name__ == "__main__":
    app = MapViewApp()
    
    # Запускаємо підключення до бекенду у фоновому потоці
    ws_thread = threading.Thread(target=start_async_loop, args=(app,), daemon=True)
    ws_thread.start()
    
    # Запускаємо вікно програми
    app.mainloop()