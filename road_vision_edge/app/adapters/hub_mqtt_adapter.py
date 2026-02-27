import logging
import paho.mqtt.client as mqtt
from app.interfaces.hub_gateway import HubGateway
from app.entities.processed_agent_data import ProcessedAgentData


class HubMqttAdapter(HubGateway):
    def __init__(self, broker: str, port: int, topic: str):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()

        self.client.on_connect = self.on_connect
        self.connect_to_broker()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info(f"Connected to Hub MQTT Broker ({self.broker}:{self.port})")
        else:
            logging.error(f"Failed to connect to Hub MQTT Broker with code {rc}")

    def connect_to_broker(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logging.error(f"Could not connect to Hub MQTT broker: {e}")

    def save_data(self, processed_data: ProcessedAgentData) -> bool:
        try:
            # Серіалізація у JSON
            payload = processed_data.model_dump_json()

            # Відправка в топік Hub
            result = self.client.publish(self.topic, payload)

            # Перевірка статусу відправки
            if result[0] == 0:
                logging.info(f"Published processed data to {self.topic}")
                return True
            else:
                logging.error(f"Failed to publish to {self.topic}")
                return False
        except Exception as e:
            logging.error(f"Error publishing to Hub MQTT: {e}")
            return False
