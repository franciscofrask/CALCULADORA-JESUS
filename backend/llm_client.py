"""
Cliente LLM mínimo sobre el SDK de OpenAI (ChatGPT).
"""
import os

from openai import AsyncOpenAI

DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class UserMessage:
    def __init__(self, text: str):
        self.text = text


class LlmChat:
    def __init__(self, api_key: str = None, session_id: str = None, system_message: str = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.session_id = session_id
        self.system_message = system_message
        self.model = DEFAULT_MODEL
        self.history = []
        self._client = None
        self.response_format = None

    def with_model(self, provider: str, model: str):
        # Se conserva la firma (provider, model) por compatibilidad con las
        # llamadas existentes. El provider se ignora: siempre usamos OpenAI.
        if model:
            self.model = model
        return self

    def with_json_mode(self, enabled: bool = True):
        """Fuerza salida JSON válida (OpenAI response_format=json_object).
        Requiere que el system/prompt mencione 'json' (ya lo hace)."""
        self.response_format = {"type": "json_object"} if enabled else None
        return self

    def _get_client(self):
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    def _build_messages(self):
        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.extend(self.history)
        return messages

    async def send_message(self, message: UserMessage) -> str:
        self.history.append({"role": "user", "content": message.text})
        client = self._get_client()

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self._build_messages(),
        }
        if self.response_format:
            kwargs["response_format"] = self.response_format

        response = await client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content
        self.history.append({"role": "assistant", "content": text})
        return text
