import os
import requests
from dotenv import load_dotenv

load_dotenv()


class LLMProvider:

    def __init__(self):

        self.api_url = os.getenv(
            "OLLAMA_API_URL",
            "http://localhost:11434/api/chat"
        )

        self.model = os.getenv(
            "OLLAMA_MODEL",
            "gpt-oss:120b-cloud"
        )

    def generate_response(self, messages):

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        response = requests.post(
            self.api_url,
            json=payload,
            timeout=180
        )

        response.raise_for_status()

        data = response.json()

        return data["message"]["content"]