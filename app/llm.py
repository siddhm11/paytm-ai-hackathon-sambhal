"""Thin LLM client: Sarvam (default), any OpenAI-compatible endpoint, or Anthropic."""
from __future__ import annotations

import json
import re
import time

import httpx

from . import config

STATS = {"calls": 0, "errors": 0, "last_ms": None, "last_error": None}
MAX_TOKENS = 1500   # room for reasoning models, which spend tokens thinking before the JSON answer


def available() -> bool:
    return config.llm_enabled()


def _extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise ValueError(f"no JSON in model output: {text[:120]!r}")
        return json.loads(m.group(0))


def _openai_style(system: str, user: str, json_mode: bool) -> str:
    headers = {"Content-Type": "application/json"}
    headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    if config.LLM_PROVIDER == "sarvam":          # Sarvam's docs list both headers; send both
        headers["api-subscription-key"] = config.LLM_API_KEY
    body = {"model": config.LLM_MODEL, "temperature": 0.2, "max_tokens": MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if config.LLM_REASONING_EFFORT:      # "none" is sent as null, which turns thinking off
        body["reasoning_effort"] = None if config.LLM_REASONING_EFFORT == "none" else config.LLM_REASONING_EFFORT
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    r = httpx.post(url, headers=headers, json=body, timeout=config.LLM_TIMEOUT)
    if r.status_code == 400 and json_mode:      # some models reject response_format: retry plain
        body.pop("response_format", None)
        r = httpx.post(url, headers=headers, json=body, timeout=config.LLM_TIMEOUT)
    if r.status_code == 402 and config.LLM_PROVIDER == "sarvam":     # out of credits: rules reader from now on
        config.RUNTIME["sarvam_out"] = True
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def _anthropic(system: str, user: str) -> str:
    r = httpx.post(
        config.LLM_BASE_URL.rstrip("/") + "/messages",
        headers={"x-api-key": config.LLM_API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": config.LLM_MODEL, "max_tokens": MAX_TOKENS, "temperature": 0.2, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=config.LLM_TIMEOUT,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", []))


def chat_json(system: str, user: str) -> dict:
    if not available():
        raise RuntimeError("LLM not configured")
    t0 = time.time()
    STATS["calls"] += 1
    try:
        if config.LLM_PROVIDER == "anthropic":
            out = _anthropic(system + "\nReply with JSON only.", user)
        else:
            out = _openai_style(system, user, json_mode=True)
        res = _extract_json(out)
        STATS["last_ms"] = int((time.time() - t0) * 1000)
        return res
    except Exception as e:
        STATS["errors"] += 1
        STATS["last_error"] = str(e)[:200]
        raise
