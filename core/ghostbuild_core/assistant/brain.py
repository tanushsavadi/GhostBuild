"""The thing that talks. `Brain` is a protocol so the rest of the code never knows which model (or fake) is behind it.

AnthropicBrain uses the official SDK with structured outputs (a JSON schema per reply type). It runs in a worker thread (the caller
owns that); every call has a hard timeout and raises BrainError on any failure so the caller can fall back to the deterministic path."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Protocol, TypeVar

from pydantic import BaseModel

from .schemas import IntakeReply, StepReply

log = logging.getLogger("ghostbuild.assistant.brain")
T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-5-5"  # measured: the only model that got electrical-safety answers right; override with GB_BRAIN_MODEL (e.g. claude-haiku-5-5 is ~2x faster, less reliable)
TIMEOUT_S = 20.0


class BrainError(Exception):
    """The brain could not answer (no key, network, timeout, refusal, bad output). The message never contains secrets."""


class Brain(Protocol):
    name: str

    def intake(self, system: str, messages: list[dict]) -> IntakeReply: ...

    def step(self, system: str, messages: list[dict]) -> StepReply: ...


class AnthropicBrain:
    def __init__(self, model: Optional[str] = None, client=None, effort: str = "low") -> None:
        self.model = model or os.environ.get("GB_BRAIN_MODEL") or DEFAULT_MODEL
        self.effort = os.environ.get("GB_BRAIN_EFFORT", effort)
        self.name = f"anthropic:{self.model}"
        self._client = client
        self.last_ms = 0

    @property
    def client(self):
        if self._client is None:
            import anthropic  # dependency group `knowledge`; imported lazily so core runs without it

            self._client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=1)
        return self._client

    def _call(self, system: str, messages: list[dict], model_cls: type[T]) -> T:
        started = time.monotonic()
        try:
            resp = self.client.messages.parse(
                model=self.model, max_tokens=900, system=system, messages=messages, output_format=model_cls,
                output_config={"effort": self.effort},
            )
        except Exception as exc:  # SDK errors are typed, but every one of them means "use the fallback"
            raise BrainError(f"{type(exc).__name__}") from None
        self.last_ms = int((time.monotonic() - started) * 1000)
        if getattr(resp, "stop_reason", "") == "refusal":
            raise BrainError("refused")
        out = getattr(resp, "parsed_output", None)
        if out is None:
            raise BrainError("no structured output")
        return out

    def intake(self, system: str, messages: list[dict]) -> IntakeReply:
        return self._call(system, messages, IntakeReply)

    def step(self, system: str, messages: list[dict]) -> StepReply:
        return self._call(system, messages, StepReply)


class FakeBrain:
    """Scripted brain for tests and offline demos: pops replies in order (or calls a function). Records what it was asked."""

    name = "fake"

    def __init__(self, intake=None, step=None, delay_s: float = 0.0) -> None:
        self._intake, self._step = list(intake or []), list(step or [])
        self.delay_s = delay_s
        self.calls: list[tuple[str, str, list[dict]]] = []

    def _next(self, queue: list, kind: str, system: str, messages: list[dict]):
        self.calls.append((kind, system, messages))
        if self.delay_s:
            time.sleep(self.delay_s)
        if not queue:
            raise BrainError("fake brain has no more replies")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(messages) if callable(item) else item

    def intake(self, system: str, messages: list[dict]) -> IntakeReply:
        return self._next(self._intake, "intake", system, messages)

    def step(self, system: str, messages: list[dict]) -> StepReply:
        return self._next(self._step, "step", system, messages)


def brain_from_env() -> Optional[Brain]:
    """AnthropicBrain when a key is configured and the assistant is not switched off (GB_ASSISTANT=0); else None (deterministic only)."""
    if os.environ.get("GB_ASSISTANT", "1") == "0" or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    return AnthropicBrain()
