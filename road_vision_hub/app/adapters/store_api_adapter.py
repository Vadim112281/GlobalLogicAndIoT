import json
import logging
from typing import List
import requests
from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.store_gateway import StoreGateway

class StoreApiAdapter(StoreGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_data(self, processed_agent_data_batch: List[ProcessedAgentData]) -> bool:
        url = f"{self.api_base_url}/processed_agent_data/"
        try:
            payload = [json.loads(item.model_dump_json()) for item in processed_agent_data_batch]
            response = requests.post(url, json=payload)
            response.raise_for_status()
            logging.info(f"Успешно сохранено {len(processed_agent_data_batch)} записей.")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка сохранения: {e}")
            return False
    pass