"""Core LLM client supporting NVIDIA NIM API (integrate.api.nvidia.com) and Local Ollama
with automatic .env discovery, JSON extraction, retries, disk caching, and secret stripping."""

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.prompts import SYSTEM_JSON_ONLY

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent


def _load_dotenv_files() -> None:
    """Automatically load .env files from project root, backend/, parent directory, or cwd."""
    candidates = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        BACKEND_DIR / ".env",
        REPO_ROOT.parent / ".env",
        REPO_ROOT / ".env.local",
        BACKEND_DIR / ".env.local",
    ]
    for env_path in candidates:
        try:
            if env_path.is_file():
                for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k and v:
                            # If user put an nvapi- key under any variable name, also expose as NVIDIA_API_KEY
                            if v.startswith("nvapi-") and not os.environ.get("NVIDIA_API_KEY"):
                                os.environ["NVIDIA_API_KEY"] = v
                            if k not in os.environ:
                                os.environ[k] = v
                    elif line.startswith("nvapi-") and not os.environ.get("NVIDIA_API_KEY"):
                        os.environ["NVIDIA_API_KEY"] = line
        except Exception:
            pass


_load_dotenv_files()


def get_nvidia_api_key() -> str:
    """Return NVIDIA API key from environment or .env files if configured."""
    _load_dotenv_files()
    for key_name in (
        "NVIDIA_API_KEY",
        "NVAPI_KEY",
        "NVIDIA_KEY",
        "NGC_API_KEY",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "FALLBACK_LLM_KEY",
    ):
        val = (os.environ.get(key_name) or "").strip()
        if val:
            return val
    # Also check if any env var value starts with nvapi-
    for _, val in os.environ.items():
        if isinstance(val, str) and val.strip().startswith("nvapi-"):
            return val.strip()
    return ""


def get_nvidia_base_url() -> str:
    return (
        os.environ.get("NVIDIA_BASE_URL")
        or os.environ.get("NVIDIA_API_URL")
        or os.environ.get("FALLBACK_LLM_URL")
        or "https://integrate.api.nvidia.com/v1"
    ).rstrip("/")


def get_nvidia_model() -> str:
    model = (
        os.environ.get("NVIDIA_MODEL")
        or os.environ.get("LLM_MODEL")
        or "meta/llama-3.1-70b-instruct"
    ).strip()
    # If OLLAMA_MODEL was set to an NVIDIA model name (contains '/'), honor it
    ollama_m = (os.environ.get("OLLAMA_MODEL") or "").strip()
    if "/" in ollama_m and "qwen2.5-coder:" not in ollama_m:
        return ollama_m
    return model


def set_runtime_nvidia_key(api_key: str, model: str | None = None) -> None:
    """Set NVIDIA API key at runtime and persist to REPO_ROOT/.env so it survives restarts."""
    clean_key = api_key.strip()
    os.environ["NVIDIA_API_KEY"] = clean_key
    if model and model.strip():
        os.environ["NVIDIA_MODEL"] = model.strip()
    try:
        env_file = REPO_ROOT / ".env"
        existing = env_file.read_text(encoding="utf-8", errors="ignore") if env_file.exists() else ""
        lines = [
            ln for ln in existing.splitlines()
            if not ln.strip().startswith(("NVIDIA_API_KEY=", "NVIDIA_MODEL="))
        ]
        lines.append(f"NVIDIA_API_KEY={clean_key}")
        if model and model.strip():
            lines.append(f"NVIDIA_MODEL={model.strip()}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not persist NVIDIA_API_KEY to .env: %s", exc)


# Legacy constants kept for compatibility
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
FALLBACK_API_URL = os.getenv("FALLBACK_LLM_URL", "")
FALLBACK_API_KEY = os.getenv("FALLBACK_LLM_KEY", "")
CACHE_DIR = Path(os.getenv("LLM_CACHE_DIR", ".llm_cache"))

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token|auth[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]+['\"]?"),
    re.compile(r"(?m)^([A-Z0-9_]+)\s*=\s*(.+)$"),
]


def strip_secrets(text: str) -> str:
    """Remove sensitive .env values and hardcoded keys before sending text to the LLM."""
    cleaned = SECRET_PATTERNS[0].sub(r"\1=[REDACTED]", text)

    def _redact_env(match: re.Match) -> str:
        key = match.group(1)
        if any(w in key.upper() for w in ("KEY", "SECRET", "TOKEN", "PASS", "URL", "DB", "AUTH")):
            return f"{key}=[REDACTED]"
        return match.group(0)

    return SECRET_PATTERNS[1].sub(_redact_env, cleaned)


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from LLM text, handling markdown code fences or leading prose."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _compute_cache_key(messages: list[dict[str, str]], model: str, schema_name: str) -> str:
    raw = json.dumps({"messages": messages, "model": model, "schema": schema_name}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_cache(key: str) -> dict[str, Any] | None:
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _write_cache(key: str, data: dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{key}.json"
        cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to write LLM cache: %s", exc)


async def chat(
    messages: list[dict[str, str]],
    schema: Type[T] | None = None,
    timeout: float = 60.0,
    fallback_factory: Callable[[], T | dict[str, Any]] | None = None,
) -> T | dict[str, Any]:
    """Send a chat request to NVIDIA NIM (if API key configured) or Ollama, with JSON validation, disk cache, and fallback."""
    sanitized_messages = [
        {"role": m.get("role", "user"), "content": strip_secrets(m.get("content", ""))}
        for m in messages
    ]
    if not any(m["role"] == "system" for m in sanitized_messages):
        sanitized_messages.insert(0, {"role": "system", "content": SYSTEM_JSON_ONLY})

    nvidia_key = get_nvidia_api_key()
    active_model = get_nvidia_model() if nvidia_key else OLLAMA_MODEL
    schema_name = schema.__name__ if schema else "dict"
    cache_key = _compute_cache_key(sanitized_messages, active_model, schema_name)

    cached = _read_cache(cache_key)
    if cached is not None:
        try:
            return (schema.model_validate(cached) if hasattr(schema, "model_validate") else schema.parse_obj(cached)) if schema else cached
        except ValidationError:
            pass

    last_error: Exception | None = None

    # Priority 1: NVIDIA NIM API (if NVIDIA_API_KEY / nvapi-... is configured)
    if nvidia_key:
        base_url = get_nvidia_base_url()
        endpoint = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
        candidate_models = [active_model]
        for fallback_m in ("meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct", "qwen/qwen2.5-coder-32b-instruct"):
            if fallback_m not in candidate_models:
                candidate_models.append(fallback_m)

        headers = {
            "Authorization": f"Bearer {nvidia_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        for model_name in candidate_models[:2]:
            nv_payload: dict[str, Any] = {
                "model": model_name,
                "messages": sanitized_messages,
                "temperature": 0.1,
                "max_tokens": 2048,
            }
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=timeout) as http_client:
                        resp = await http_client.post(endpoint, headers=headers, json=nv_payload)
                        resp.raise_for_status()
                        body = resp.json()
                        choices = body.get("choices") or []
                        raw_content = choices[0].get("message", {}).get("content", "{}") if choices else "{}"
                        parsed = _extract_json_object(raw_content)

                        if schema is not None:
                            validated = schema.model_validate(parsed) if hasattr(schema, "model_validate") else schema.parse_obj(parsed)
                            _write_cache(cache_key, validated.model_dump() if hasattr(validated, "model_dump") else validated.dict())
                            return validated

                        _write_cache(cache_key, parsed)
                        return parsed
                except Exception as exc:
                    last_error = exc
                    logger.warning("NVIDIA NIM (%s) attempt %d/2 failed: %s", model_name, attempt + 1, exc)

    # Priority 2: Local Ollama (only if NVIDIA key was not set or failed)
    ollama_payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": sanitized_messages,
        "format": "json",
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.1},
    }

    max_ollama_attempts = 1 if nvidia_key else 2
    for attempt in range(max_ollama_attempts):
        try:
            async with httpx.AsyncClient(timeout=min(timeout, 8.0)) as http_client:
                resp = await http_client.post(f"{OLLAMA_URL.rstrip('/')}/api/chat", json=ollama_payload)
                resp.raise_for_status()
                body = resp.json()
                raw_content = body.get("message", {}).get("content", "{}")
                parsed = _extract_json_object(raw_content)

                if schema is not None:
                    validated = schema.model_validate(parsed) if hasattr(schema, "model_validate") else schema.parse_obj(parsed)
                    _write_cache(cache_key, validated.model_dump() if hasattr(validated, "model_dump") else validated.dict())
                    return validated

                _write_cache(cache_key, parsed)
                return parsed
        except (httpx.HTTPError, json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning("Ollama call attempt %d/%d failed: %s", attempt + 1, max_ollama_attempts, exc)

    logger.error("All LLM attempts failed (%s). Using deterministic fallback.", last_error)
    if fallback_factory is not None:
        return fallback_factory()

    raise RuntimeError(f"LLM request failed: {last_error}")