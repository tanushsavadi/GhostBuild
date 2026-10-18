"""Optional hold-to-ask voice lane (flag --voice / GB_VOICE=1; default OFF).

Flow: G2 long-press -> plugin sends G2Input hold_start (LISTENING) and streams PCM to WS /ws/voice -> on release the plugin sends
{"type":"end"} and hold_end (THINKING) -> STT final transcript -> deterministic intent (intent.py) -> a short answer built only from
the active Repair Card, or the existing help navigation / goal resolver. Every HUD frame still comes from hud.py (layer "voice").

Hard rules: audio is only relayed to the STT provider, never written to disk or logged (only the transcript text is logged, with the
provider name and its true origin); a voice command never commits a physical state or clears a fault; any failure degrades to an
honest VOICE UNAVAILABLE / USE TOUCH frame and the touch path keeps working untouched.

Provider: ElevenLabs Scribe v2 realtime through integrations/elevenlabs/client.py.
Only deliberate, consented PTT utterances are committed; audio is never stored locally.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Callable, Optional, Protocol

from contracts.models import Cue, GoalRequest
from integrations.elevenlabs.client import ElevenLabsStt, VoiceProviderError, elevenlabs_factory

from . import goal as goal_mod
from . import intent as intent_mod
from .hud import Screen

if TYPE_CHECKING:  # pragma: no cover
    from .runtime import Runtime

log = logging.getLogger("ghostbuild.voice")

TIMEOUT_MS = 8000  # no transcript this long after release -> DIDN'T CATCH THAT
LISTEN_CAP_MS = 15000  # plugin caps a hold at 10 s; core never stays in LISTENING forever
RESULT_TTL_MS = 5000
NO_SOCKET_MS = 2000  # released, but the plugin never opened /ws/voice (mic/socket failed before it could say so): fallback now
MAX_AUDIO_BYTES = 640_000  # 20 s of 16 kHz s16le mono; anything beyond is dropped
FINALIZE_TIMEOUT_S = 7.0


def voice_enabled_from_env() -> bool:
    return os.environ.get("GB_VOICE", "").strip() == "1"


# --------------------------------------------------------------------------- providers
ProviderUnavailable = VoiceProviderError


class SttProvider(Protocol):
    name: str
    origin: str  # true origin of the transcript: "elevenlabs_stt" | "fake_test"

    async def start(self) -> None: ...
    async def feed(self, frame: bytes) -> None: ...
    async def finalize(self) -> str: ...
    async def close(self) -> None: ...


class FakeStt:
    """TEST DOUBLE. Returns a scripted transcript if any audio was fed. Not microphone-derived; its origin says so."""

    name = "FakeStt"
    origin = "fake_test"

    def __init__(self, transcript: str = "", *, fail_start: bool = False, fail_finalize: bool = False, delay_s: float = 0.0) -> None:
        self.transcript = transcript
        self.fail_start, self.fail_finalize, self.delay_s = fail_start, fail_finalize, delay_s
        self.frames = 0
        self.bytes = 0
        self.closed = False

    async def start(self) -> None:
        if self.fail_start:
            raise ProviderUnavailable("FakeStt scripted start failure")

    async def feed(self, frame: bytes) -> None:
        self.frames += 1
        self.bytes += len(frame)

    async def finalize(self) -> str:
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.fail_finalize:
            raise RuntimeError("FakeStt scripted finalize failure")
        return self.transcript if self.bytes else ""

    async def close(self) -> None:
        self.closed = True


# --------------------------------------------------------------------------- service
class VoiceService:
    def __init__(
        self,
        runtime: "Runtime",
        provider_factory: Callable[[], SttProvider] = elevenlabs_factory,
        *,
        timeout_ms: int = TIMEOUT_MS,
        listen_cap_ms: int = LISTEN_CAP_MS,
        result_ttl_ms: int = RESULT_TTL_MS,
    ) -> None:
        self.rt = runtime
        self.provider_factory = provider_factory
        self.timeout_ms, self.listen_cap_ms, self.result_ttl_ms = timeout_ms, listen_cap_ms, result_ttl_ms
        self.state = "idle"  # idle | listening | thinking | result
        self._deadline = 0
        self._released_at = 0
        self.socket_started = False
        self._active_socket: object | None = None
        self._utterance_context: tuple | None = None
        self._last_reply_text = ""
        self._transcript_accepted = False
        runtime.voice = self

    # ---------------------------------------------------------------- HUD (hud.py is the only writer)
    def _now(self) -> int:
        return self.rt.clock.now_ms()

    def _show(self, cue: Cue, ttl_ms: Optional[int], state: str) -> None:
        self.state = state
        self.rt.hud.set_layer("voice", Screen.ask(cue, ttl_ms=ttl_ms))
        self.rt.hud.sync()

    def _clear(self) -> None:
        self.state = "idle"
        self.rt.hud.set_layer("voice", None)
        self.rt.hud.sync()

    def _result(self, cue: Cue) -> None:
        self._deadline = self._now() + self.result_ttl_ms
        self._show(cue, self.result_ttl_ms, "result")

    # ---------------------------------------------------------------- G2 gestures
    def on_hold(self, gesture: str) -> None:
        sess = self.rt.sessions.active
        if sess is None or sess.phase == "welcome":
            return
        if gesture == "hold_start":
            self.rt.sessions.wake()  # the wearer is talking to us: the front screen stays lit afterwards
            if self.state in ("listening", "thinking"):
                return  # duplicate start cannot extend recording indefinitely
            self._utterance_context = self._context_key()
            self.socket_started = False
            self._deadline = self._now() + self.listen_cap_ms
            self._show(intent_mod.LISTENING, None, "listening")
        elif gesture == "hold_end" and self.state == "listening":
            self._released_at = self._now()
            self._deadline = self._now() + self.timeout_ms
            self._show(intent_mod.THINKING, None, "thinking")

    def need_consent(self) -> None:
        self._result(intent_mod.CONSENT)

    def unavailable(self, reason: str) -> None:
        if self.state in ("idle", "listening", "thinking", "result"):
            self.rt.elog.write("voice_unavailable", reason=reason)
            self._result(intent_mod.UNAVAILABLE)

    def tick(self) -> None:
        if self.state == "thinking" and not self.socket_started and self._now() - self._released_at >= NO_SOCKET_MS:
            self.unavailable("released without an audio socket")
            return
        if self.state in ("listening", "thinking") and self._now() >= self._deadline:
            self.rt.elog.write("voice_timeout", state=self.state)
            self._result(intent_mod.DIDNT_CATCH)
        elif self.state == "result" and self._now() >= self._deadline:
            self._clear()

    def _context_key(self) -> tuple:
        """Capture the actual task before STT: a late utterance cannot act on a later step."""
        sess = self.rt.sessions.active
        pb = self.rt.playbook
        if pb is not None:
            return (sess.id if sess else None, id(pb), pb.index, pb.done, tuple(pb.confirmed), tuple(pb.verified))
        tr = self.rt.engine.current_track()
        return (sess.id if sess else None, sess.phase if sess else None,
                self.rt.engine.card.card_id, tr.test.id if tr else None, tr.check_idx if tr else None)

    # ---------------------------------------------------------------- transcript -> reply
    def on_transcript(self, text: str, provider: str, origin: str) -> None:
        self._transcript_accepted = False
        self._last_reply_text = ""
        if self.state not in ("listening", "thinking"):
            return  # late (after the timeout screen) or unsolicited: ignored
        if self._utterance_context is not None and self._utterance_context != self._context_key():
            self.rt.elog.write("voice_ignored", reason="task changed while listening")
            self._clear()
            return
        self._transcript_accepted = True
        text = (text or "").strip()[:300]
        self.rt.elog.write("voice_transcript", provider=provider, origin=origin, text=text)  # transcript text only, never audio
        if not text:
            self._result(intent_mod.DIDNT_CATCH)
            return
        sess = self.rt.sessions.active
        if sess is None:
            self.unavailable("no session")
            return
        if sess.phase != "task":
            self._goal(text, sess.id, origin)
            return
        if self.rt.playbook is not None:
            self._ask_playbook(text)  # a playbook task: same deterministic follow-up as POST /ask (card text only)
            return
        intent = intent_mod.classify(text)
        if intent == "unknown" and self._goal_candidate(text, sess.id):
            self._goal(text, sess.id, origin)
            return
        self._reply(intent, text)

    def _cards(self):
        return self.rt.all_cards()

    def _goal_requests(self, text: str, sid: str) -> list[GoalRequest]:
        first = intent_mod.infer_goal_mode(text)
        other = "build" if first == "fix" else "fix"
        return [GoalRequest(session_id=sid, mode=m, via="voice", text=text) for m in (first, other)]

    def _goal_candidate(self, text: str, sid: str) -> bool:
        return any(goal_mod.resolve(r, self._cards()).status == "supported" for r in self._goal_requests(text, sid))

    def _goal(self, text: str, sid: str, origin: str) -> None:
        reqs = self._goal_requests(text, sid)
        chosen = next((r for r in reqs if goal_mod.resolve(r, self._cards()).status == "supported"), reqs[0])
        res = self.rt.resolve_goal(chosen)  # the EXISTING deterministic resolver + session flash (via="voice")
        if res is not None:
            self.rt.engine.note(f"voice goal ({origin}): {res.status}. {res.detail}", "DETERMINISTIC", {"mode": chosen.mode, "heard": text})
        self._clear()

    def _ask_playbook(self, text: str) -> None:
        self._clear()  # drop the voice overlay; the playbook shows its answer on the engine layer
        result = self.rt.ask(text)
        if result is not None:
            self._last_reply_text = result.as_json()["text"]

    def _ctx(self) -> intent_mod.Ctx:
        e = self.rt.engine
        tr = e.current_track()
        fault = check = guide = None
        idx = 0
        if tr is not None:
            fault, idx = tr.test, tr.check_idx
            check = fault.checks[min(idx, len(fault.checks) - 1)]
            if check.guide_id:
                guide = next((g for g in e.card.guides if g.id == check.guide_id), None)
        return intent_mod.Ctx(
            card=e.card, fault=fault, check=check, check_idx=idx, guide=guide,
            help_open=bool(tr and tr.help_open),
            erroring=e.state == "NO_LINK" or e.camera_status in ("unavailable", "frozen"),
            measured_pass=e.measured_pass_ok,
        )

    def _reply(self, intent: str, heard: str) -> None:
        e = self.rt.engine
        r = intent_mod.answer(intent, self._ctx())  # type: ignore[arg-type]
        self.rt.elog.write("voice_intent", intent=intent, reply=r.kind, target=r.target)
        self._last_reply_text = r.phone_text or ((r.cue.line1 + " " + r.cue.line2).strip() if r.cue else "")
        if r.phone_text:
            e.note(f"voice answer ({intent}): {r.phone_text}", r.phone_label or "DETERMINISTIC", {"heard": heard})
        if r.kind == "suppress":
            self._clear()  # an error is on screen; stay silent rather than answer confidently
        elif r.kind == "status":
            shown = e.recheck_status()
            self._clear()
            if not shown and not e.await_func and e.state == "HEALTHY":
                self._result(Cue(line1="NO DATA YET", line2="WAITING FOR PI"))
        elif r.kind == "help_goto":
            ok = e.help_goto(r.target or "")
            if ok:
                self._clear()
            else:
                self._result(r.fallback_cue or intent_mod.NOT_IN_CARD)
        else:
            self._result(r.cue or intent_mod.NOT_SURE)

    # ---------------------------------------------------------------- /ws/voice
    async def serve(self, websocket) -> None:
        """Binary PCM in, JSON control {"type":"start"|"end"|"abort"} in. Audio is relayed to the provider only (never stored)."""
        from fastapi import WebSocketDisconnect

        await websocket.accept()
        stt: Optional[SttProvider] = None
        total = 0
        owner = object()

        async def reply(obj: dict) -> None:
            try:
                await websocket.send_json(obj)
            except Exception:
                pass

        async def drop() -> None:
            nonlocal stt
            if self._active_socket is owner:
                self._active_socket = None
            s, stt = stt, None
            if s is not None:
                try:
                    await s.close()
                except Exception:
                    log.warning("provider close failed")

        async def finalize_unless_cancelled(provider: SttProvider) -> str:
            """Keep consuming cancellation while cloud STT is pending, before applying any text."""
            async def cancelled() -> None:
                while True:
                    msg = await websocket.receive()
                    if msg.get("type") == "websocket.disconnect":
                        return
                    try:
                        ctl = json.loads(msg.get("text") or "")
                    except ValueError:
                        continue
                    if isinstance(ctl, dict):
                        if ctl.get("type") == "abort":
                            return
                        if ctl.get("type") == "start":
                            await reply({"type": "busy"})
                    # Duplicate end/audio while finalizing must not start another utterance.

            result = asyncio.create_task(provider.finalize())
            cancel = asyncio.create_task(cancelled())
            try:
                done, _ = await asyncio.wait((result, cancel), return_when=asyncio.FIRST_COMPLETED)
                if cancel in done:
                    raise ProviderUnavailable("capture cancelled")
                return result.result()
            finally:
                for task in (result, cancel):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(result, cancel, return_exceptions=True)

        try:
            while True:
                msg = await asyncio.wait_for(websocket.receive(), (self.listen_cap_ms + self.timeout_ms) / 1000)
                if msg.get("type") == "websocket.disconnect":
                    break
                data = msg.get("bytes")
                if data is not None:
                    if stt is not None:
                        if len(data) % 2 or total + len(data) > MAX_AUDIO_BYTES:
                            self.unavailable("invalid or oversized PCM")
                            await drop()
                            await reply({"type": "unavailable"})
                            continue
                        total += len(data)
                        try:
                            await stt.feed(data)
                        except Exception as exc:
                            log.warning("stt feed failed: %s", type(exc).__name__)
                            self.unavailable(f"feed failed: {type(exc).__name__}")
                            await drop()
                    continue
                try:
                    ctl = json.loads(msg.get("text") or "")
                except ValueError:
                    continue
                kind = ctl.get("type") if isinstance(ctl, dict) else None
                if kind == "start":
                    if stt is not None or (self._active_socket is not None and self._active_socket is not owner):
                        await reply({"type": "busy"})
                        continue
                    await drop()
                    total = 0
                    if ctl.get("consent") is not True:
                        self.need_consent()  # no mic, no provider until the wearer has seen HOLD TO TALK / AUDIO SENT TO SERVER
                        await reply({"type": "consent_required"})
                        continue
                    self._active_socket = owner
                    if self.state != "listening":
                        self.on_hold("hold_start")  # phone PTT uses the same lifecycle without a temple event
                    if self.state != "listening":
                        self._active_socket = None
                        await reply({"type": "unavailable"})
                        continue
                    self.socket_started = True
                    try:
                        stt = self.provider_factory()
                        await stt.start()
                    except Exception as exc:
                        log.warning("stt unavailable: %s", type(exc).__name__)
                        self.unavailable(f"start failed: {type(exc).__name__}")
                        await drop()
                        await reply({"type": "unavailable"})
                elif kind == "end":
                    s, stt = stt, None
                    if s is None:
                        continue  # start failed already; the wearer saw VOICE UNAVAILABLE
                    if self.state == "listening":
                        self.on_hold("hold_end")
                    try:
                        text = await asyncio.wait_for(finalize_unless_cancelled(s), FINALIZE_TIMEOUT_S)
                    except Exception as exc:
                        log.warning("stt finalize failed: %s", type(exc).__name__)
                        self.unavailable(f"finalize failed: {type(exc).__name__}")
                        await reply({"type": "unavailable"})
                    else:
                        self.on_transcript(text, s.name, s.origin)
                        await reply({"type": "done", "origin": s.origin,
                            "transcript": text if self._transcript_accepted else "",
                            "text": self._last_reply_text,
                            "ignored": not self._transcript_accepted})
                    finally:
                        if self._active_socket is owner:
                            self._active_socket = None
                        try:
                            await s.close()
                        except Exception:
                            pass
                elif kind == "abort":
                    owned = self._active_socket is owner
                    await drop()
                    if ctl.get("reason") == "no_speech":  # a hands-free listen nobody spoke into: leave no error on the glasses
                        if owned and self.state in ("listening", "thinking"):
                            self._clear()
                        continue
                    if owned and self.state in ("listening", "thinking"):
                        self.unavailable("capture cancelled")
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.warning("voice socket failed: %s", type(exc).__name__)
        finally:
            was_active = self._active_socket is owner
            await drop()
            if was_active and self.state in ("listening", "thinking"):
                self.unavailable("audio connection closed")
