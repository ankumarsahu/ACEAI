from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import TypeVar

from openai import OpenAI

from idamp.core.config import settings


T = TypeVar("T")


def with_retry(operation: Callable[[], T], attempts: int = 3) -> T:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Operation failed after {attempts} attempts: {last_error}") from last_error


def llm_client() -> OpenAI:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured. Add it to idamp/.env.")
    return OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)


def chat_text(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    def request() -> str:
        response = llm_client().chat.completions.create(
            model=settings.groq_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The model returned an empty response.")
        return content.strip()

    return with_retry(request)


def parse_json_array(raw: str) -> list[dict[str, object]]:
    text = raw.strip()
    candidates = [text]
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
                return parsed
        except json.JSONDecodeError:
            pass
    start = text.find("[")
    if start >= 0:
        fragment = text[start:]
        last_object_end = fragment.rfind("}")
        if last_object_end >= 0:
            recovered = fragment[: last_object_end + 1].rstrip().rstrip(",") + "]"
            try:
                parsed = json.loads(recovered)
                if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
                    return parsed
            except json.JSONDecodeError:
                pass
    raise ValueError("Could not parse a JSON array from the model response.")