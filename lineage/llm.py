"""
Model client for Lineage.

One class, `LLM`, wraps every model we call (Muse Spark, Muse Wonder on Meta's
API, Muse Spark Open on Fireworks). It gives us:

- retries with backoff, so a rate limit or a blip never kills a run
- a cost ledger, so the dashboard can show dollars per lineage
- JSON parsing that tolerates reasoning models wrapping their answer in prose
- a `MockLLM` with the same interface, so the whole system can be tested
  without spending a cent
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import AsyncOpenAI, APIStatusError, RateLimitError, APIConnectionError, APITimeoutError

load_dotenv()

# Price per million tokens (input, output), Standard mode, as of Nov 2026.
# Spark Open on Fireworks is billed by Fireworks; Meta's own API price for it
# is used as the estimate. Wonder is the expensive one, so it runs rarely.
PRICES = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-wonder-1.0": (4.00, 20.00),
    "accounts/fireworks/models/muse-spark-open": (1.25, 4.15),
}

ROLE_MODELS = {
    # role -> (model, provider)
    "agent": ("muse-spark-1.3", "meta"),
    "juror_spark": ("muse-spark-1.3", "meta"),
    "juror_open": ("accounts/fireworks/models/muse-spark-open", "fireworks"),
    "arbiter": ("muse-wonder-1.0", "meta"),
}


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    by_model: dict = field(default_factory=dict)

    def add(self, model: str, inp: int, out: int) -> float:
        pin, pout = PRICES.get(model, (1.25, 4.25))
        cost = inp / 1e6 * pin + out / 1e6 * pout
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.usd += cost
        m = self.by_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0})
        m["calls"] += 1
        m["input_tokens"] += inp
        m["output_tokens"] += out
        m["usd"] += cost
        return cost

    def snapshot(self) -> dict:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "usd": round(self.usd, 4),
        }


def extract_json(text: str):
    """Pull the first JSON object or array out of a model reply.

    Reasoning models sometimes wrap JSON in prose or code fences. We find the
    first `{` or `[`, then walk forward tracking bracket depth until it closes.
    """
    if not text:
        raise ValueError("empty reply")
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError(f"no JSON in reply: {text[:120]!r}")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON in reply")


class LLM:
    """Async client over Meta Model API and Fireworks, with retries and a cost ledger."""

    def __init__(self, max_concurrency: int = 8, spend_cap_usd: float = 250.0):
        self.meta = AsyncOpenAI(
            api_key=os.environ.get("META_API_KEY", ""),
            base_url=os.environ.get("META_BASE_URL", "https://api.meta.ai/v1"),
            timeout=120,
        )
        # The open-weights juror can run on any OpenAI-compatible host of Muse Spark Open.
        # Default is Fireworks; set JUROR2_BASE_URL / JUROR2_API_KEY / JUROR2_MODEL to use
        # another provider (e.g. Baseten: https://inference.baseten.co/v1,
        # model meta-models/muse-spark-open-1026).
        j2_model = os.environ.get("JUROR2_MODEL")
        if j2_model:
            ROLE_MODELS["juror_open"] = (j2_model, "fireworks")
            PRICES.setdefault(j2_model, (1.25, 4.15))
        self.fireworks = AsyncOpenAI(
            api_key=os.environ.get("JUROR2_API_KEY") or os.environ.get("FIREWORKS_API_KEY", ""),
            base_url=os.environ.get("JUROR2_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            timeout=120,
        )
        self.juror2_host = os.environ.get("JUROR2_BASE_URL", "fireworks")
        self.usage = Usage()
        self.sem = asyncio.Semaphore(max_concurrency)
        self.spend_cap = spend_cap_usd
        # Feature flags we learn at runtime: if a provider rejects a parameter
        # once, we stop sending it rather than failing every call.
        self._supports = {"meta": {"reasoning": True, "json": True},
                          "fireworks": {"reasoning": False, "json": True}}

    def _client(self, provider: str) -> AsyncOpenAI:
        return self.meta if provider == "meta" else self.fireworks

    async def chat(self, role: str, system: str, user: str, *,
                   reasoning: str = "low", json_mode: bool = True,
                   max_tokens: int = 2000, temperature: float = 0.0) -> tuple[str, dict]:
        """Send one chat request for a role. Returns (text, meta).

        `reasoning` is "low" | "medium" | "high". Routine triage runs at low to
        save tokens; proposing edits and arbitration run higher.
        """
        if self.usage.usd >= self.spend_cap:
            raise RuntimeError(f"spend cap ${self.spend_cap} reached (${self.usage.usd:.2f})")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        delay = 2.0
        last_err: Exception | None = None
        for attempt in range(6):
            # Resolved inside the loop so a retry can switch providers after a billing error.
            model, provider = ROLE_MODELS[role]
            if provider == "fireworks" and getattr(self, "_fireworks_down", False):
                model, provider = "muse-spark-1.3", "meta"      # degraded: same family, different call
            client = self._client(provider)
            sup = self._supports[provider]
            kwargs: dict = dict(model=model, messages=messages, max_tokens=max_tokens,
                                temperature=temperature)
            if json_mode and sup["json"]:
                kwargs["response_format"] = {"type": "json_object"}
            if sup["reasoning"]:
                kwargs["reasoning_effort"] = reasoning
            try:
                async with self.sem:
                    t0 = time.time()
                    r = await client.chat.completions.create(**kwargs)
                text = r.choices[0].message.content or ""
                u = r.usage
                cost = self.usage.add(model, u.prompt_tokens, u.completion_tokens)
                return text, {"model": model, "input_tokens": u.prompt_tokens,
                              "output_tokens": u.completion_tokens, "usd": round(cost, 5),
                              "seconds": round(time.time() - t0, 2)}
            except APIStatusError as e:
                last_err = e
                msg = str(e).lower()
                # Unsupported parameter: learn and retry immediately without it.
                if e.status_code == 400 and "reasoning" in msg and sup["reasoning"]:
                    sup["reasoning"] = False
                    continue
                if e.status_code == 400 and "response_format" in msg and sup["json"]:
                    sup["json"] = False
                    continue
                if provider == "fireworks" and e.status_code in (401, 402, 404, 412):
                    if not getattr(self, "_fireworks_down", False):
                        print(f"!! juror-2 provider error ({e.status_code}: {str(e)[:80]}); routing {role} to Meta API for the rest of this run")
                    self._fireworks_down = True
                    continue
                if e.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(delay + random.random())
                    delay = min(delay * 2, 30)
                    continue
                raise
            except (RateLimitError, APIConnectionError, APITimeoutError) as e:
                last_err = e
                await asyncio.sleep(delay + random.random())
                delay = min(delay * 2, 30)
        raise RuntimeError(f"gave up after retries: {last_err}")

    async def chat_json(self, role: str, system: str, user: str, **kw):
        text, meta = await self.chat(role, system, user, **kw)
        if not text.strip():
            # Reasoning models spend output tokens thinking; if the budget ran out
            # before the answer, retry with a bigger budget and less reasoning.
            kw2 = dict(kw, max_tokens=max(kw.get("max_tokens", 2000) * 3, 6000), reasoning="low")
            text, meta2 = await self.chat(role, system, user, **kw2)
            meta["usd"] += meta2["usd"]
        try:
            return extract_json(text), meta
        except ValueError:
            # One repair attempt: ask the same model to re-emit valid JSON only.
            text2, meta2 = await self.chat(role, "Return only valid JSON. No prose.",
                                           f"Convert this to valid JSON:\n{text[:4000]}",
                                           reasoning="low", max_tokens=kw.get("max_tokens", 2000))
            meta["usd"] += meta2["usd"]
            return extract_json(text2), meta


class MockLLM(LLM):
    """Offline stand-in with the same interface.

    It triages by keyword, proposes plausible edits, and judges consistently,
    so the full pipeline, event log and dashboard can be exercised for free.
    Pass `handler` to override behaviour in tests.
    """

    def __init__(self, handler=None, latency: float = 0.0):
        self.usage = Usage()
        self.sem = asyncio.Semaphore(64)
        self.spend_cap = 1e9
        self.handler = handler
        self.latency = latency
        self._supports = {"meta": {"reasoning": True, "json": True},
                          "fireworks": {"reasoning": False, "json": True}}

    async def chat(self, role, system, user, *, reasoning="low", json_mode=True,
                   max_tokens=2000, temperature=0.0):
        if self.latency:
            await asyncio.sleep(self.latency)
        model, _ = ROLE_MODELS[role]
        text = self.handler(role, system, user) if self.handler else default_mock(role, system, user)
        cost = self.usage.add(model, len(system + user) // 4, len(text) // 4)
        return text, {"model": model, "input_tokens": len(system + user) // 4,
                      "output_tokens": len(text) // 4, "usd": round(cost, 5), "seconds": 0.0}


def default_mock(role: str, system: str, user: str) -> str:
    """Deterministic fake behaviour used by tests and `--mock` runs."""
    if "TASK: propose_edit" in user:
        return json.dumps({"op": "add", "rule_id": None,
                           "text": "If the title mentions 'panic' or 'crash', kind is bug.",
                           "reason": "Several crash reports in this batch were misfiled."})
    if "TASK: arbitrate" in user:
        return json.dumps({"decision": "reject", "reason": "Validation gain is within noise."})
    if "TASK: triage" in user:
        # Keyword triage: good enough to make curves move in mock runs.
        m = re.search(r"KINDS: (.*)\nAREAS: (.*)\n", user)
        kinds = [k.strip() for k in m.group(1).split(",")] if m else ["bug"]
        areas = [a.strip() for a in m.group(2).split(",")] if m else ["node"]
        items = re.findall(r"ISSUE (\S+):\s*(.*)", user)
        out = []
        for iid, title in items:
            t = title.lower()
            kind = "bug" if any(w in t for w in ("fail", "crash", "panic", "error", "broken")) else (
                "feature" if any(w in t for w in ("add", "support", "allow")) else kinds[0])
            area = next((a for a in areas if a.split("/")[-1] in t), areas[hash(iid) % len(areas)])
            out.append({"id": iid, "kind": kind if kind in kinds else kinds[0], "area": area,
                        "confidence": 0.7, "rule_ids": []})
        return json.dumps({"decisions": out})
    return "{}"