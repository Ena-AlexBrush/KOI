from __future__ import annotations

import json
import os
from typing import Any

import httpx
from pydantic import ValidationError


OLLAMA_URL = "https://ollama.com/api/chat"
OLLAMA_WEB_SEARCH_URL = "https://ollama.com/api/web_search"
OLLAMA_WEB_FETCH_URL = "https://ollama.com/api/web_fetch"


class ModelCallError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


async def web_search(query: str, *, max_results: int = 5, timeout: float = 25.0) -> list[dict[str, str]]:
    """Search the public web through Ollama and return linkable source snippets."""
    api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if not api_key:
        raise ModelCallError("model_error", "OLLAMA_API_KEY is unset. Add it to backend/.env to use live web search.")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(OLLAMA_WEB_SEARCH_URL, headers=headers, json={"query": query, "max_results": max_results})
    except httpx.TimeoutException as exc:
        raise ModelCallError("timeout", "Ollama web search timed out.") from exc
    except httpx.HTTPError as exc:
        raise ModelCallError("model_error", f"Ollama web search request failed: {exc}") from exc
    if response.status_code >= 400:
        raise ModelCallError("model_error", f"Ollama web search returned HTTP {response.status_code}: {response.text[:300]}")
    try:
        payload = response.json()
        items = payload.get("results", [])
        return [
            {"title": str(item.get("title", "Untitled result")), "url": str(item.get("url", "")), "content": str(item.get("content", ""))[:1400]}
            for item in items
            if isinstance(item, dict) and str(item.get("url", "")).startswith(("https://", "http://"))
        ]
    except (ValueError, AttributeError, TypeError) as exc:
        raise ModelCallError("model_error", "Ollama web search returned an unreadable response.") from exc


async def web_fetch(url: str, *, timeout: float = 25.0) -> dict[str, str]:
    """Fetch the readable text of a URL returned by Ollama web search."""
    api_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if not api_key:
        raise ModelCallError("model_error", "OLLAMA_API_KEY is unset. Add it to backend/.env to fetch web sources.")
    if not url.startswith("https://"):
        raise ModelCallError("model_error", "Only HTTPS search result pages can be fetched.")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(OLLAMA_WEB_FETCH_URL, headers=headers, json={"url": url})
    except httpx.TimeoutException as exc:
        raise ModelCallError("timeout", "Ollama web page fetch timed out.") from exc
    except httpx.HTTPError as exc:
        raise ModelCallError("model_error", f"Ollama web page fetch failed: {exc}") from exc
    if response.status_code >= 400:
        raise ModelCallError("model_error", f"Ollama web fetch returned HTTP {response.status_code}: {response.text[:300]}")
    try:
        payload = response.json()
        return {"title": str(payload.get("title", "")), "content": str(payload.get("content", ""))[:3200]}
    except (ValueError, AttributeError, TypeError) as exc:
        raise ModelCallError("model_error", "Ollama web fetch returned an unreadable response.") from exc


def model_name() -> str:
    value = os.getenv("OLLAMA_MODEL", "").strip()
    if not value:
        raise ModelCallError("model_error", "OLLAMA_MODEL is unset. Set it to a model name confirmed in your Ollama Cloud account.")
    return value


async def call_json(messages: list[dict[str, str]], validator: Any, *, post_validate: Any = None, timeout: float = 120.0) -> tuple[dict[str, Any], int]:
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
                raise ModelCallError("timeout", f"Ollama Cloud did not respond within {timeout:g} seconds. Showing web search results directly when available.") from exc
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

