"""Session product discovery. Workers return data; only pump/commands change UI state."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue

from contracts.models import Cue, GoalResolution, ImageRef

from ..cache import digest, terms
from ..hud import Screen
from . import attrs as a
from .models import Candidate, DiscoveryState, Timings

log = logging.getLogger("ghostbuild.discovery")
ACTIVE = {
    "searching",
    "choosing",
    "confirming",
    "asking",
    "configuring",
    "loading",
    "no_match",
    "unavailable",
}


def short(text, n=24):
    return re.sub(
        r"[^A-Z0-9 ./'?,:!()+-]",
        "",
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper(),
    )[:n]


class ProductDiscoveryService:
    def __init__(
        self, runtime, sources, *, path=None, timeout_s=22, live=True, research=False
    ):
        self.rt = runtime
        self.sources = {s.id: s for s in sources}
        self.path = Path(path) if path else None
        self.timeout_s = timeout_s
        self.live = live
        self.research = research
        self.compiled = set()  # guides compiled from a confirmed product's manual: identified by that selection
        self.states = {}
        self.pools = {}
        self.remembered = {}
        self.jobs = {}
        self.started = {}
        self._serial = 0
        self.results = Queue()
        self.workers = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="product-discovery"
        )
        self.cards = {}
        self._rows = {}
        self._busy = {}
        self.sheet_images = {}
        self.query_keys = {}
        # Product cards resolve on reconnect but never enter the general task catalogue.
        for source in sources:
            for rec in source.cached():
                bundle = source.bundle(rec)
                if bundle:
                    for card in bundle.all_cards():
                        self.cards[card.card_id] = card
        self._load()
        runtime.discovery = self
        runtime.sessions.restore()
        self._render_active()

    def _load(self):
        if self.path and self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.remembered = data.get("remembered", {})
                from .models import ProductRecord

                self.pools = {
                    sid: [ProductRecord.model_validate(r) for r in rows]
                    for sid, rows in data.get("pools", {}).items()
                }
                for sid, raw in data.get("states", {}).items():
                    s = DiscoveryState.model_validate(raw)
                    if s.live_state == "running":
                        s.live_state = "failed"
                        s.notice = (
                            "Live search interrupted; saved matches remain available."
                        )
                    if s.phase in ("searching", "loading"):
                        s.phase = "choosing" if s.candidates else "unavailable"
                    self.states[sid] = s
            except Exception:
                log.exception("could not restore discovery")

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "states": {k: s.model_dump(mode="json") for k, s in self.states.items()},
            "pools": {
                k: [r.model_dump(mode="json") for r in rows]
                for k, rows in self.pools.items()
            },
            "remembered": self.remembered,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(self.path)

    def state(self, sid):
        return self.states.get(sid, DiscoveryState(session_id=sid))

    def active(self, sid):
        return self.state(sid).phase in ACTIVE

    def requires_identification(self, card):
        return card.card_id not in self.cards and card.card_id not in self.compiled and any(src.wants(card.title + " " + " ".join(card.aliases)) for src in self.sources.values())

    def names_other_product(self, sid, text):
        """While a product guide is open: does the person name a different product line than the selected one?"""
        s = self.state(sid)
        if s.selected is None or s.source not in self.sources:
            return False
        attrs = a.extract(text, self.sources[s.source].known_names())
        return bool(attrs.name_hint and a.norm(attrs.name_hint) != a.norm(s.selected.name))

    def correct(self, sid, text):
        s = self.state(sid)
        src = s.source
        category, color = s.attrs.category, s.attrs.color
        self.cancel(sid)
        self.states[sid] = DiscoveryState(session_id=sid, source=src)
        self.states[sid].attrs.category = category
        self.states[sid].attrs.color = color
        self.rt.assistant.cancel(sid)
        self.rt.assistant.intakes.pop(sid, None)
        self.rt.sessions.active.phase = "menu"
        if self.rt.playbook:
            self.rt.playbook.detach()
            self.rt.playbook, self.rt._pb_sid = None, None
        self._lookup_or_rank(sid, text)

    def wants(self, req):
        return bool(
            req.text
            and (
                self.active(req.session_id)
                or any(s.wants(req.text) for s in self.sources.values())
            )
        )

    def _invalidate(self, sid):
        self._serial += 1
        self.jobs[sid] = self._serial
        self._busy.pop(sid, None)
        return self._serial

    def _job(self, sid, kind, fn):
        job = self._invalidate(sid)
        self._busy[sid] = (job, time.monotonic(), kind)

        def work():
            try:
                result = fn()
                error = None
            except Exception:
                log.exception("product retrieval failed")
                result = None
                error = "Official retrieval is unavailable. Try an article number or product link."
            self.results.put((sid, job, kind, result, error))

        self.workers.submit(work)

    def submit(self, req):
        sid = req.session_id
        task = self.rt.assistant.tasks.get(sid)
        if task:
            task.record("IDENTIFY_PRODUCT", "Use real source records and confirm identity before a manual")
            task.critical_unknowns = ["Confirmed product identity and required assembly configuration"]
        if sid not in self.rt.sessions.sessions:
            return None
        sess = self.rt.sessions.sessions[sid]
        if sess.phase == "task" and self.rt.playbook is not None:
            self.rt.playbook.detach()
            self.rt.playbook = None
            self.rt._pb_sid = None
        sess.phase = "menu"
        self.rt.assistant.cancel(sid)
        if not self.active(sid):
            source = next(
                (s for s in self.sources.values() if s.wants(req.text or "")), None
            )
            if source is None:
                return None
            self.started[sid] = time.monotonic()
            self.states[sid] = DiscoveryState(
                session_id=sid,
                source=source.id,
                source_label=source.label,
                query=req.text or "",
            )
            self.pools[sid] = source.cached()
            self._lookup_or_rank(sid, req.text or "", initial=True)
        else:
            self.utterance(sid, req.text or "")
        return self.resolution(sid)

    def resolution(self, sid):
        s = self.state(sid)
        return GoalResolution(
            session_id=sid,
            status="supported" if s.phase == "ready" else "ambiguous",
            mode="build",
            card_id=s.card_id,
            cue=Cue(
                line1="GUIDE READY" if s.phase == "ready" else "FIND YOUR PRODUCT",
                line2=short(s.message, 26),
            ),
            detail=s.message,
            alternatives=[c.record.name for c in s.candidates],
        )

    def _cache_covers(self, s):
        """Use saved candidates when official facts cover the requested attributes."""
        if not self.rt.cache.enabled or not s.candidates or s.attrs.is_empty():
            return False
        src = self.sources[s.source]
        requested = terms(" ".join(s.attrs.words)) - terms(src.id + " " + src.label)
        for c in s.candidates:
            r = c.record
            if c.conflicts or c.unverified:
                continue
            if s.attrs.name_hint and a.norm(r.name) != a.norm(s.attrs.name_hint):
                continue
            now_ms = getattr(src, "now_ms", lambda: int(time.time() * 1000))()
            if not r.verified_at or now_ms - r.verified_at > 14 * 24 * 3600 * 1000:
                continue
            facts = terms(
                " ".join(
                    [
                        r.name,
                        r.type_name,
                        r.color,
                        r.size,
                        r.description,
                        *r.evidence,
                        *r.manual_evidence,
                    ]
                )
            )
            if requested <= facts:
                return True
        return False

    def _lookup_or_rank(self, sid, text, initial=False):
        self.started[sid] = time.monotonic()
        s = self.states[sid]
        src = self.sources[s.source]
        s.timings = Timings()
        claim = src.claim(text)
        self._invalidate(sid)
        s.focus = None
        s.page = 0
        s.question = None
        s.pending = None
        if claim:
            s.phase = "searching"
            s.message = "Looking up the exact article or product link."
            self._job(sid, "exact", lambda: src.lookup(claim, self.timeout_s))
        else:
            t = time.perf_counter()
            extra = a.extract(text, src.known_names())
            # Describing what the existing object has is a feature refinement,
            # not a change from e.g. a desk to its cabinet.
            if s.attrs.category and re.match(
                r"^(?:(?:mine|it|this|that)\s+(?:also\s+)?has\b|with\b)",
                a.norm(text),
            ):
                extra.category = None
            s.attrs = s.attrs.merged(extra)
            s.query = s.attrs.describe() or text
            self.query_keys[sid] = digest(
                {
                    "source": s.source,
                    "words": sorted(terms(" ".join(s.attrs.words))),
                    "attributes": s.attrs.model_dump(exclude={"words"}),
                }
            )
            self._rank(sid)
            s.timings.cache_ms = round((time.perf_counter() - t) * 1000)
            s.search_mode = "cache"
            s.timings.total_ms = s.timings.cache_ms
            remembered = self.rt.cache.get("products", self.query_keys[sid])
            saved_ok = bool(
                remembered
                and s.candidates
                and set(remembered.get("articles", []))
                & {
                    c.record.article
                    for c in s.candidates
                    if c.record.verified_at
                    and int(time.time() * 1000) - c.record.verified_at
                    <= 14 * 24 * 3600 * 1000
                }
            )
            if saved_ok or self._cache_covers(s):
                s.live_state = "off"
                s.notice = (
                    "Using saved verified matches. Search again if these do not fit."
                )
            elif self.live and src.live_available():
                s.live_state = "running"
                s.search_mode = "cache+live" if s.candidates else "live"
                if not s.candidates:
                    s.phase = "searching"
                self._search(sid)
            else:
                s.live_state = "unavailable" if self.live else "off"
                if not s.candidates:
                    s.phase = "unavailable"
                    s.message = "No saved match. Live search is unavailable. Enter the article number or official product link."
        self._changed(sid)

    def _origin(self, rec):
        day = (
            datetime.fromtimestamp(rec.verified_at / 1000, UTC).strftime("%Y-%m-%d")
            if rec.verified_at
            else "unknown date"
        )
        return (
            ("Live official-site search; page read " + day)
            if rec.how == "live_search"
            else "Cached; read from official site " + day
        )

    def _rank(self, sid, skip=()):
        s = self.states[sid]
        ruled_out = {x.lower() for x in s.attrs.excluded_names}
        s.candidates = a.rank(
            [r for r in self.pools.get(sid, [])
             if r.article not in skip and r.name.lower() not in ruled_out
             and (not s.attrs.name_hint or a.norm(r.name) == a.norm(s.attrs.name_hint))], s.attrs
        )
        for c in s.candidates:
            c.origin = self._origin(c.record)
        s.focus = None
        s.page = 0
        self._rows[sid] = 0
        s.phase = "choosing" if s.candidates else "no_match"
        s.message = (
            "Which one matches yours? Pick a photo, say its number or name, or describe more."
            if s.candidates
            else "No validated match. Try another detail, an article number or an official product link."
        )

    def _search(self, sid):
        s = self.states[sid]
        src = self.sources[s.source]
        query = a.search_query(s.attrs, s.query)
        s.live_state = "running"
        self._job(sid, "search", lambda: src.search(query, self.timeout_s, set()))

    def pump(self):
        for sid, (job, t0, kind) in list(self._busy.items()):
            if time.monotonic() - t0 > self.timeout_s:
                self._invalidate(sid)
                s = self.states[sid]
                s.live_state = "failed"
                s.notice = (
                    "Official retrieval timed out. Saved matches remain available."
                )
                if s.phase == "searching":
                    s.phase = "unavailable"
                    s.message = "Lookup timed out. Try the article number or official product link."
                self._changed(sid)
        while True:
            try:
                sid, job, kind, result, error = self.results.get_nowait()
            except Empty:
                break
            if self.jobs.get(sid) != job:
                continue
            self._busy.pop(sid, None)
            s = self.states[sid]
            if not self.active(sid):
                continue
            if error:
                s.notice = error
                s.live_state = "failed"
                if s.phase == "searching":
                    s.phase = "unavailable"
                    s.message = error
            elif kind == "exact":
                s.timings.exact_ms = result.ms
                if result.record:
                    s.pending = Candidate(
                        record=result.record, rank=1, score=0, origin=result.origin
                    )
                    s.candidates = [s.pending]
                    s.phase = "confirming"
                    s.message = f"Is this your {result.record.name} ({result.record.article_display or result.record.article})?"
                    self.pools[sid] = [result.record, *self.pools.get(sid, [])]
                else:
                    s.phase = "no_match"
                    s.message = (
                        result.error
                        or "No exact product found. Check the number or link."
                    )
            else:
                s.timings.search_ms = result.search_ms
                s.timings.validate_ms = result.validate_ms
                s.timings.provider = result.provider
                s.live_state = (
                    "unavailable"
                    if result.unavailable
                    else "failed"
                    if result.error
                    else "done"
                )
                s.notice = result.error or ""
                if result.records and not result.error and sid in self.query_keys:
                    self.rt.cache.put(
                        "products",
                        self.query_keys[sid],
                        {"articles": [r.article for r in result.records]},
                        ttl=14 * 24 * 3600,
                    )
                fresh = {r.article: r for r in self.pools[sid]}
                fresh.update({r.article: r for r in result.records})
                self.pools[sid] = list(fresh.values())
                # Keep spoken ordinals and focused pictures stable while the wearer is choosing.
                if s.phase == "searching" or not s.candidates:
                    self._rank(sid)
                elif result.records:
                    s.notice = "Live search complete. Current choices kept in place; use Show more for other matches."
                if not s.candidates and result.unavailable:
                    s.phase = "unavailable"
            s.timings.total_ms = round(
                (time.monotonic() - self.started.get(sid, time.monotonic())) * 1000
            )
            self._changed(sid)

    def utterance(self, sid, text):
        s = self.states[sid]
        src = self.sources[s.source]
        if src.claim(text):
            self._lookup_or_rank(sid, text)
            return
        if s.phase == "configuring":
            opts = s.config_question.options
            picked = [
                o
                for o in opts
                if re.search(r"\b" + re.escape(o.id) + r"\b", text.lower())
                or text.lower() == o.label.lower()
            ]
            idx = a.pick_ordinal(text, len(opts))
            if len(picked) == 1:
                self.configure(sid, picked[0].id)
            elif idx is not None:
                self.configure(sid, opts[idx].id)
            else:
                s.message = s.config_question.prompt
                self._changed(sid)
            return
        if s.pending and a.is_yes(text):
            self.select(sid, s.pending.record.article)
            return
        if a.is_none(text) or (s.pending and a.is_no(text)):
            self.none(sid)
            return
        if a.is_more(text):
            self.more(sid)
            return
        if a.says_has_number(text):
            s.message = (
                "Type or say the article number, or paste the official product link."
            )
            self._changed(sid)
            return
        if s.question:
            extra = a.answer_to_attrs(s.question, text)
            s.question = None
            if extra is not None:
                s.attrs = s.attrs.merged(extra)
                self._rank(sid)
                self._changed(sid)
                return
        idx = a.pick_ordinal(text, len(s.candidates))
        matches = a.pick_name(text, [c.record.name for c in s.candidates])
        if idx is not None:
            self.select(sid, s.candidates[idx].record.article)
            return
        if len(matches) == 1:
            self.select(sid, s.candidates[matches[0]].record.article)
            return
        if len(matches) > 1:
            choices = [s.candidates[i] for i in matches]
            best = choices[0]
            if not best.conflicts and all(
                set(best.matched) > set(c.matched) and best.score - c.score >= 2
                for c in choices[1:]
            ):
                self.select(sid, best.record.article)
                return
            # Ask which real variant; do not silently choose among articles sharing a name.
            s.candidates = [s.candidates[i] for i in matches]
            s.pending = None
            s.phase = "choosing"
            for i, c in enumerate(s.candidates):
                c.rank = i + 1
            s.message = "Several articles share that name. Pick the photo and article number that match yours."
            self._changed(sid)
            return
        self._lookup_or_rank(sid, text)

    def none(self, sid):
        s = self.states[sid]
        self._invalidate(sid)
        s.pending = None
        s.focus = None
        s.question = a.distinguishing_question(s.candidates, s.attrs)
        s.phase = "asking" if s.question else "no_match"
        s.message = (
            s.question.prompt
            if s.question
            else "What is different? Add a detail, article number or official product link."
        )
        self._changed(sid)

    def refresh_search(self, sid):
        s = self.states[sid]
        if not self.live or not self.sources[s.source].live_available():
            s.live_state = "unavailable"
            s.notice = "Live search is unavailable. The saved matches and number/link lookup still work."
            self._changed(sid)
            return
        self.started[sid] = time.monotonic()
        s.notice = "Searching the official site again at your request."
        if not s.candidates:
            s.phase = "searching"
        self._search(sid)
        self._changed(sid)

    def more(self, sid):
        self.started[sid] = time.monotonic()
        s = self.states[sid]
        s.seen = list(
            dict.fromkeys([*s.seen, *[c.record.article for c in s.candidates]])
        )
        self._rank(sid, s.seen)
        if not s.candidates and self.live and self.sources[s.source].live_available():
            s.phase = "searching"
            self._search(sid)
        self._changed(sid)

    def select(self, sid, article):
        s = self.states[sid]
        rec = next(
            (c.record for c in s.candidates if c.record.article == article), None
        )
        if rec is None:
            raise ValueError("Choose a current candidate.")
        self._invalidate(sid)
        s.live_state = "off" if s.live_state == "running" else s.live_state
        s.selected = rec
        s.pending = None
        s.question = None
        s.focus = None
        b = self.sources[s.source].bundle(rec)
        if b is None:
            s.phase = "unavailable"
            s.message = "Product confirmed. Its official manual is linked below; an offline step guide has not been prepared yet."
            goal = f"Assemble {rec.name} ({rec.article}) following the official manual"
            saved = self.rt.cache.guide(goal, "build") if rec.manual_verified and rec.manual_url else None
            if saved is not None:  # compiled from this manual before: start it now, no second paid compile
                card, review = saved
                if all(c.card_id != card.card_id for c in self.rt.cards):
                    self.rt.cards = [*self.rt.cards, card]
                if review:
                    self.rt.live.cards.setdefault(card.card_id, review)
                if self.rt.sessions.start_card(sid, card, echo=False):
                    self._confirmed(sid, card, f"{rec.name} guide ready: compiled from the official manual, not human-reviewed.")
                    return
            if self.research and rec.manual_verified and rec.manual_url:
                from contracts.models import GoalRequest

                req = GoalRequest(session_id=sid, mode="build", via="phone_text", text=goal)
                if self.rt.live.try_start(
                    req, doc_urls=[rec.manual_url, rec.product_url]
                ):
                    s.phase = "loading"  # the glasses show the research progress screen, then the guide starts itself
                    s.message = "Preparing a step-by-step guide from the official manual. It starts by itself when ready; AI-compiled, not human-reviewed."
            self._changed(sid)
            if s.phase != "loading":  # never a silent return to the photo list after THIS ONE
                self.rt.sessions.flash_message(sid, Cue(line1="NO STEP GUIDE YET", line2="MANUAL ON YOUR PHONE"), 6000)
            return
        s.config_question = b.config_question
        key = f"{rec.source}:{rec.article}"
        s.config = dict(self.remembered.get(key, {}))
        if b.config_question and s.config.get(b.config_question.id) not in [
            o.id for o in b.config_question.options
        ]:
            s.phase = "configuring"
            s.message = b.config_question.prompt
            self._rows[sid] = 0
            self._changed(sid)
        else:
            self._start(sid, b)

    def configure(self, sid, option):
        s = self.states[sid]
        q = s.config_question
        if (
            s.phase != "configuring"
            or q is None
            or option not in [o.id for o in q.options]
        ):
            raise ValueError("Choose one of the configuration options.")
        s.config[q.id] = option
        self.remembered[f"{s.selected.source}:{s.selected.article}"] = dict(s.config)
        self._start(sid, self.sources[s.source].bundle(s.selected))

    def _start(self, sid, b):
        s = self.states[sid]
        option = s.config.get(b.config_question.id) if b.config_question else None
        card = b.load_card(option)
        self.cards[card.card_id] = card
        if not self.rt.sessions.start_card(sid, card, echo=False):
            raise ValueError("Session changed; start discovery again.")
        self._confirmed(sid, card, f"{s.selected.name} guide ready. Manual step numbers match this guide.")

    def research_finished(self, sid, card):
        """The guide compiled from a confirmed product's manual finished (card) or failed (None)."""
        s = self.states.get(sid)
        if s is None or s.phase != "loading" or s.selected is None:
            return
        if card is None:
            s.phase = "unavailable"
            s.message = "Could not prepare a step guide from the official manual. The manual is linked below."
            self._changed(sid)
            return
        self.compiled.add(card.card_id)
        self._confirmed(sid, card, f"{s.selected.name} guide ready: compiled from the official manual, not human-reviewed.")

    def _confirmed(self, sid, card, message):
        s = self.states[sid]
        self.compiled.add(card.card_id) if card.card_id not in self.cards else None
        s.card_id = card.card_id
        s.phase = "ready"
        s.message = message
        task = self.rt.assistant.tasks.get(sid)
        if task:
            from ..assistant.adaptive import TaskFact
            task.merge([TaskFact(field="product", value=s.selected.name + " " + s.selected.article, origin="user", quote="")])
            # Adapter-confirmed selection and document facts have their own provenance.
            task.facts = [f for f in task.facts if f.field not in ("product", "model", "configuration")]
            task.facts.append(TaskFact(field="product", value=s.selected.name + " " + s.selected.article, origin="user", quote="Explicit photo/article selection", confidence=1))
            task.facts.append(TaskFact(field="configuration", value=json.dumps(s.config), origin="user", quote="Selected manual configuration", confidence=1))
            task.critical_unknowns = []
            task.sources = list(dict.fromkeys([s.selected.product_url, s.selected.manual_url] + task.sources))
            self.rt.assistant._persist()
        self._changed(sid)

    def cancel(self, sid):
        self._invalidate(sid)
        self.states[sid] = DiscoveryState(session_id=sid)
        self._changed(sid)

    def _changed(self, sid):
        self.states[sid].updated_ms = self.rt.clock.now_ms()
        self._save()
        if self.rt.sessions.active_id == sid:
            self._render_active()

    def refresh(self):
        self._render_active()

    def _render_active(self):
        sid = self.rt.sessions.active_id
        if sid:
            preparing = self.state(sid).phase == "loading"  # the research progress screen shows instead
            self.rt.sessions.show_discovery(
                sid, self.screen(sid) if self.active(sid) and not preparing else None
            )

    def _options(self, s):
        if s.phase == "configuring":
            return [o.label for o in s.config_question.options]
        if s.question:
            return s.question.options
        if s.pending:
            return ["YES - THIS ONE", "NO - REFINE"]
        if s.candidates:
            if s.page == 0:
                return [
                    f"{i + 1} {short(c.record.name + ' ' + c.record.color, 20)}"
                    for i, c in enumerate(s.candidates[:3])
                ] + ["MORE"]
            return [
                f"{i + 4} {short(c.record.name + ' ' + c.record.color, 20)}"
                for i, c in enumerate(s.candidates[3:5])
            ] + ["BACK", "NONE OF THESE"]
        return []

    def screen(self, sid):
        s = self.state(sid)
        if s.focus is not None and 0 <= s.focus < len(s.candidates):
            c = s.candidates[s.focus]
            r = c.record
            # Image bytes/hash come from the same local cache used by the HTTP route.
            from .images import photo

            data = photo(self.rt.asset_root, r, True)
            cue = Cue(
                line1=short(f"{s.focus + 1}/{len(s.candidates)} {r.name}"),
                line2="PRESS: THIS ONE",
            )
            if data:
                return Screen.visual(
                    cue,
                    ImageRef(
                        guide_id=f"product_{r.source}_{r.article}",
                        view="where",
                        index=0,
                        count=1,
                        title=short(r.name),
                        url=f"/discovery/img/{r.source}/{r.article}.g2.png",
                        w=288,
                        h=144,
                        sha256=hashlib.sha256(data).hexdigest(),
                        provenance="MANUFACTURER DOC",
                        step_id="product",
                    ),
                )
            return Screen.intervene(cue, immediate=True)
        opts = self._options(s)
        if (
            opts
            and s.candidates
            and not s.pending
            and not s.question
            and s.phase != "configuring"
        ):
            from .images import shortlist

            row = min(self._rows.get(sid, 0), len(opts) - 1)
            visible = s.candidates[:3] if s.page == 0 else s.candidates[3:5]
            offset = 0 if s.page == 0 else 3
            data = shortlist(
                self.rt.asset_root, [c.record for c in visible], row, offset
            )
            if data:
                if row < len(visible):
                    rec = visible[row].record
                    cue = Cue(
                        line1=short(
                            f"{offset + row + 1}/{len(s.candidates)} {rec.name} {rec.color}"
                        ),
                        line2="PRESS: ENLARGE PHOTO",
                    )
                else:
                    cue = Cue(line1=short(opts[row]), line2="PRESS TO CHOOSE")
                digest = hashlib.sha256(data).hexdigest()
                self.sheet_images[digest] = data
                while len(self.sheet_images) > 64:
                    self.sheet_images.pop(next(iter(self.sheet_images)))
                return Screen.visual(
                    cue,
                    ImageRef(
                        guide_id="product_matches",
                        view="where",
                        index=0,
                        count=1,
                        title="PRODUCT MATCHES",
                        url=f"/discovery/shortlist/{digest}.png",
                        w=288,
                        h=144,
                        sha256=digest,
                        provenance="MANUFACTURER DOC",
                        step_id="product_matches",
                    ),
                )
        if opts:
            return Screen.make_menu(
                short(s.config_question.short_prompt or s.config_question.prompt)
                if s.phase == "configuring"
                else short(s.question.prompt)
                if s.question
                else "YOUR PRODUCT?"
                if s.pending
                else "PICK YOUR PRODUCT",
                opts,
                min(self._rows.get(sid, 0), len(opts) - 1),
            )
        return Screen.intervene(
            Cue(
                line1="SEARCHING OFFICIAL SITE"
                if s.phase == "searching"
                else "ADD A NUMBER OR LINK",
                line2="SAVED MATCHES ON PHONE"
                if s.candidates
                else "OR REFINE ON PHONE",
            ),
            immediate=True,
        )

    def handle_input(self, gi):
        sid = self.rt.sessions.active_id
        if not sid or not self.active(sid) or self.rt.sessions.active.phase != "menu":
            return False
        s = self.states[sid]
        if s.phase == "loading":
            return False  # the progress screen owns the gestures; never act on the hidden photo list
        g = gi.gesture
        if g not in ("press", "swipe_down", "swipe_up"):
            return True
        if s.focus is not None:
            if g == "press":
                self.select(sid, s.candidates[s.focus].record.article)
                return True
            if g == "swipe_down":
                s.focus = (s.focus + 1) % len(s.candidates)
            else:
                s.focus = None
        else:
            opts = self._options(s)
            row = self._rows.get(sid, 0)
            if g == "swipe_up" and row == 0:
                self.cancel(sid)
                return True
            if g == "swipe_down":
                self._rows[sid] = min(row + 1, max(0, len(opts) - 1))
            elif g == "swipe_up":
                self._rows[sid] = max(0, row - 1)
            elif opts:
                label = opts[row]
                if s.phase == "configuring":
                    self.configure(sid, s.config_question.options[row].id)
                    return True
                elif s.question:
                    self.utterance(sid, label)
                    return True
                elif s.pending:
                    if row == 0:
                        self.select(sid, s.pending.record.article)
                    else:
                        self.none(sid)
                    return True
                elif label == "MORE":
                    s.page = 1
                    self._rows[sid] = 0
                elif label == "BACK":
                    s.page = 0
                    self._rows[sid] = 0
                elif label == "NONE OF THESE":
                    self.none(sid)
                    return True
                else:
                    s.focus = row + (3 if s.page else 0)
        self._changed(sid)
        return True

    def close(self):
        self.workers.shutdown(wait=False, cancel_futures=True)
