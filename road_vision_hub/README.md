Лабораторна робота #3
Hub для моніторингу стану дорожнього покриття
Опис
Даний проєкт є реалізацією Hub частини системи моніторингу стану дорожнього покриття.

Hub виконує роль проміжного мікросервісу, який акумулює дані від Agent або Edge Data Logic, тимчасово зберігає їх у пам'яті (Redis) для формування пакетів (батчів), та відправляє оброблені пакети даних до бази даних через Store API.

Hub може отримувати проаналізовані дані двома шляхами:

через MQTT брокер

через HTTP POST запити

Дані включають:

стан дороги (road_state: "small pits", "normal", тощо)

дані акселерометра (x, y, z)

GPS координати (longitude, latitude)

час отримання даних

Архітектура
Agent / Edge Logic → MQTT / HTTP → FastAPI (Hub) → Redis (тимчасовий кеш) → StoreApiAdapter (HTTP POST) → Store API (PostgreSQL)

Структура проєкту
app/

adapters/store_api_adapter.py — адаптер для відправки HTTP запитів до Store API

entities/ — доменні моделі (Pydantic схеми для валідації JSON)

interfaces/store_gateway.py — інтерфейс для взаємодії зі Store

docker/

docker-compose.yaml — конфігурація для розгортання Hub, Redis, Mosquitto та Store

Dockerfile — інструкція збірки образу для Hub

main.py — основний файл запуску (FastAPI та MQTT клієнт)
config.py — конфігурація середовища (змінні оточення)
requirements.txt — залежності проєкту
README.md — опис проєкту

Реалізація Hub логіки
Hub відповідає за прийом, кешування та пакетну передачу даних.

Основні процеси:

Накопичення даних (Redis)
При отриманні даних (через MQTT або HTTP), Hub валідує їх за допомогою Pydantic моделі ProcessedAgentData та додає у чергу Redis за допомогою команди lpush.

Пакетна відправка (Batching)
Після кожного додавання запису перевіряється довжина черги redis_client.llen().
Якщо кількість записів досягає значення BATCH_SIZE (задається в конфігурації), Hub:

витягує задану кількість записів з Redis (lpop)

формує масив об'єктів

викликає метод save_data у StoreApiAdapter

StoreApiAdapter
Реалізує інтерфейс StoreGateway. Перетворює масив Pydantic об'єктів у JSON та виконує HTTP POST запит до мікросервісу Store для збереження даних у PostgreSQL.

Інтеграція протоколів (MQTT та HTTP)
HTTP (FastAPI)
Ендпоінт для отримання даних:
POST /processed_agent_data/

MQTT (Mosquitto)
Hub підписаний на topic:
processed_data_topic

Формат повідомлення (JSON):

JSON
{
  "road_state": "small pits",
  "agent_data": {
    "accelerometer": { "x": 1.2, "y": 0.5, "z": 9.8 },
    "gps": { "latitude": 50.4504, "longitude": 30.5245 },
    "timestamp": "2026-02-27T12:00:00Z"
  }
}
Запуск
Використовується Docker. Конфігурація піднімає одразу весь ланцюг: Mosquitto, Redis, PostgreSQL, pgAdmin, мікросервіси Store та Hub.

Команди:

cd docker

docker-compose up --build

Перевірка
Переконатися в працездатності можна декількома способами:

Відправка даних:

Через Swagger UI Hub-а: http://localhost:9000/docs

Через MQTT Explorer (Host: localhost, Port: 1883, Topic: processed_data_topic)

Перевірка збереження:

Через Swagger UI Store-а: http://localhost:8000/docs (GET запит)

Через pgAdmin: http://localhost:5050 (Таблиця processed_agent_data у БД test_db)

Висновок
Було реалізовано мікросервіс Hub, який приймає проаналізовані дані сенсорів через MQTT та HTTP.

Було реалізовано механізм тимчасового накопичення даних за допомогою Redis та їх пакетної відправки.

Hub успішно інтегрований з мікросервісом Store та працює у спільному Docker-середовищі.