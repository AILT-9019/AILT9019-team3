from __future__ import annotations

import httpx

from app.config import get_settings


class LLMError(RuntimeError):
    pass


def chat_completion(system: str, user: str, *, repair: bool = False) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise LLMError(
            "LLM_API_KEY is not configured. Set it in .env or use EXTRACTOR_MODE=mock."
        )

    if repair:
        user = (
            f"{user}\n\n"
            "Your previous response was invalid. Return only valid JSON matching the schema."
        )

    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.llm_base_url}/chat/completions"

    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code == 400:
            payload.pop("response_format", None)
            response = client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            snippet = response.text[:500]
            raise LLMError(f"LLM request failed ({response.status_code}): {snippet}")
        data = response.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response did not contain choices[0].message.content") from exc

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        content = "".join(parts)

    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM returned empty content")
    return content
