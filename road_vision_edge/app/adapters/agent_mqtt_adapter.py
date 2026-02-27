import logging
import paho.mqtt.client as mqtt
from app.interfaces.agent_gateway import AgentGateway
from app.interfaces.hub_gateway import HubGateway
from app.entities.agent_data import AgentData
from app.usecases.data_processing import process_agent_data


class AgentMQTTAdapter(AgentGateway):
    def __init__(
        self, broker_host: str, broker_port: int, topic: str, hub_gateway: HubGateway
    ):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.hub_gateway = hub_gateway
        self.client = mqtt.Client()

        # Прив'язка колбеків
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info(
                f"Connected to Agent MQTT Broker ({self.broker_host}:{self.broker_port})"
            )
            self.client.subscribe(self.topic)
            logging.info(f"Subscribed to topic: {self.topic}")
        else:
            logging.error(f"Failed to connect to Agent MQTT Broker with code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            logging.info(f"Received message on {msg.topic}")

            # Десеріалізація вхідних даних (використовуємо Pydantic v2 як в Лаб 3)
            agent_data = AgentData.model_validate_json(payload, strict=True)

            # Первинна обробка
            processed_data = process_agent_data(agent_data)

            # Відправка проаналізованих даних на Hub
            if not self.hub_gateway.save_data(processed_data):
                logging.warning("Failed to save data to Hub")

        except Exception as e:
            logging.error(f"Error processing message from Agent: {e}")

    def connect(self):
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
        except Exception as e:
            logging.error(f"Could not connect to Agent MQTT broker: {e}")

    def start(self):
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()
