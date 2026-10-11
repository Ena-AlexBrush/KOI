from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import ValidationError


OLLAMA_URL = "https://ollama.com/api/chat"


class ModelCallError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def model_name() -> str:
    value = os.getenv("OLLAMA_MODEL", "").strip()
    if not value:
        raise ModelCallError("model_error", "OLLAMA_MODEL is unset. Set it to a model name confirmed in your Ollama Cloud account.")
    return value


async def call_json(messages: list[dict[str, str]], validator: Any, *, post_validate: Any = None, timeout: float = 45.0) -> tuple[dict[str, Any], int]:
    api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if not api_key:
        raise ModelCallError("model_error", "OLLAMA_API_KEY is unset. Copy backend/.env.example to backend/.env and add your key.")
    model = model_name()
    schema = validator.model_json_schema()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(2):
            try:
                response = await client.post(OLLAMA_URL, headers=headers, json={"model": model, "messages": messages, "stream": False})
            except httpx.TimeoutException as exc:
                raise ModelCallError("timeout", "Ollama Cloud call timed out.") from exc
            except httpx.HTTPError as exc:
                raise ModelCallError("model_error", f"Ollama Cloud request failed: {exc}") from exc
            if response.status_code >= 400:
                raise ModelCallError("model_error", f"Ollama Cloud returned HTTP {response.status_code}: {response.text[:300]}")
            try:
                content = response.json()["message"]["content"]
                data = json.loads(content)
                validated = validator.model_validate(data)
                if post_validate:
                    post_validate(validated.model_dump(mode="json"))
                return validated.model_dump(mode="json"), attempt
            except (KeyError, ValueError, ValidationError, TypeError) as exc:
                if attempt == 1:
                    raise ModelCallError("invalid_output", f"Model response failed JSON/Pydantic validation after one repair attempt: {exc}") from exc
                messages = [*messages, {"role": "assistant", "content": content if "content" in locals() else ""}, {"role": "user", "content": f"Repair your last answer. Return only valid JSON matching this schema exactly: {json.dumps(schema)}. Validation error: {exc}"}]
    raise ModelCallError("invalid_output", "No valid model response was produced.")

