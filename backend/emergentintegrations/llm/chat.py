"""
Stub for emergentintegrations.llm.chat using Anthropic SDK directly.
"""
import anthropic


class UserMessage:
    def __init__(self, text: str):
        self.text = text


class LlmChat:
    def __init__(self, api_key: str, session_id: str = None, system_message: str = None):
        self.api_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self.model = "claude-sonnet-4-5-20250929"
        self.history = []
        self._client = None

    def with_model(self, provider: str, model: str):
        self.model = model
        return self

    def _get_client(self):
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def send_message(self, message: UserMessage) -> str:
        self.history.append({"role": "user", "content": message.text})
        client = self._get_client()
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": self.history,
        }
        if self.system_message:
            kwargs["system"] = self.system_message

        response = await client.messages.create(**kwargs)
        text = response.content[0].text
        self.history.append({"role": "assistant", "content": text})
        return text
