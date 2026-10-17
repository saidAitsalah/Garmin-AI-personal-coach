"""The only module that talks to an LLM. Swap providers here and nothing else changes."""
from __future__ import annotations

import logging
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from .config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

RETRYABLE_CODES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


class LLMError(RuntimeError):
    pass


def generate_structured(system: str, prompt: str, schema: type[T]) -> T:
    """One Gemini call that must return JSON matching `schema`. Retries transient failures."""
    from google import genai
    from google.genai import errors, types

    s = get_settings()
    if not s.gemini_api_key:
        raise LLMError("GEMINI_API_KEY is missing in .env")

    client = genai.Client(api_key=s.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.4,
    )
    last: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = client.models.generate_content(model=s.gemini_model, contents=prompt, config=config)
            if isinstance(resp.parsed, schema):
                return resp.parsed
            return schema.model_validate_json(resp.text or "")
        except ValidationError as e:  # model returned malformed JSON: try again
            last = e
            log.warning("Gemini returned invalid JSON (attempt %d): %s", attempt + 1, e)
        except errors.APIError as e:
            last = e
            if e.code not in RETRYABLE_CODES:
                raise LLMError(f"Gemini API error {e.code}: {e}") from e
            log.warning("Gemini transient error %s (attempt %d)", e.code, attempt + 1)
            time.sleep(2 ** (attempt + 1))
        except Exception as e:
            raise LLMError(f"Gemini call failed: {e}") from e
    raise LLMError(f"Gemini failed after {MAX_ATTEMPTS} attempts: {last}")
