import json
import logging
from typing import Tuple, Dict

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GptClient:
    def __init__(self):
        self.base_url = settings.GPT_SERVICE_URL
        self.api_key = settings.GPT_SERVICE_API_KEY
        self.session = requests.Session()

    def send_request(self, prompt: str, engine: str, is_json: bool = False, asynchronous: bool = False) -> Tuple[
        Dict, int]:
        """
        Send a request to the GPT service
        :param prompt: The prompt to send to the service
        :param engine: The engine to use for the request
        :param is_json: Whether the response should be JSON
        :param asynchronous: Whether the request should be asynchronous
        """
        data = {
            "request": prompt,
            "engine": engine,
            "is_json": is_json,
            "asynchronous": asynchronous,
            "key": self.api_key,
        }
        endpoint = f"{self.base_url}/request/"
        try:
            response = self.session.post(url=endpoint, json=data)
            response.raise_for_status()
            return response.json()
        except json.JSONDecodeError as e:
            return {
                "error": f"Error decoding JSON: {e}",
                "message": response.text,
            }, response.status_code
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Error: {e}",
                "message": "An error occurred while sending the request",
            }, 500
        except Exception as e:
            return {
                "error": f"Unknown error: {e}",
                "message": "An unknown error occurred",
            }, 500

    def get_request(self, request_id: str) -> Tuple[Dict, int]:
        """
        Get the result of a previously sent request
        :param request_id: The ID of the request to get
        """
        endpoint = f"{self.base_url}/request/{request_id}/"
        params = {
            "key": self.api_key,
        }
        try:
            response = self.session.get(url=endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except json.JSONDecodeError as e:
            return {
                "error": f"Error decoding JSON: {e}",
                "message": response.text,
            }, response.status_code
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Error: {e}",
                "message": "An error occurred while sending the request",
            }, 500
        except Exception as e:
            return {
                "error": f"Unknown error: {e}",
                "message": "An unknown error occurred",
            }, 500

    def cancel_request(self, request_id: str) -> Tuple[Dict, int]:
        """
        Cancel a previously sent request
        :param request_id: The ID of the request to cancel
        """
        endpoint = f"{self.base_url}/request/{request_id}/cancel/"
        data = {
            "key": self.api_key,
        }
        try:
            response = self.session.post(url=endpoint, json=data)
            response.raise_for_status()
            return response.json()
        except json.JSONDecodeError as e:
            return {
                "error": f"Error decoding JSON: {e}",
                "message": response.text,
            }, response.status_code
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Error: {e}",
                "message": "An error occurred while sending the request",
            }, 500
        except Exception as e:
            return {
                "error": f"Unknown error: {e}",
                "message": "An unknown error occurred",
            }, 500

    def delete_request(self, request_id: str) -> Tuple[Dict, int]:
        """
        Delete a previously sent request
        :param request_id: The ID of the request to delete
        """
        endpoint = f"{self.base_url}/request/{request_id}/"
        params = {
            "key": self.api_key,
        }
        try:
            response = self.session.delete(url=endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except json.JSONDecodeError as e:
            return {
                "error": f"Error decoding JSON: {e}",
                "message": response.text,
            }, response.status_code
        except requests.exceptions.RequestException as e:
            return {
                "error": f"Error: {e}",
                "message": "An error occurred while sending the request",
            }, 500
        except Exception as e:
            return {
                "error": f"Unknown error: {e}",
                "message": "An unknown error occurred",
            }, 500
