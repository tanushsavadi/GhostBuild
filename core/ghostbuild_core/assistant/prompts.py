"""Pure builders for what a brain is told. No IO. Everything the model sees is assembled here so it can be reviewed and tested."""

from __future__ import annotations

from typing import Iterable, Optional

from contracts.models import Card, Step

from .schemas import Message, Note, Profile

SCOPE = (
    "Scope: low-voltage hobby electronics and single-board-computer accessories, paper and craft builds, small household, bike, 3D-printer and "
    "similar fixes. Decline kindly, and suggest a qualified professional, for mains electricity, gas, lithium-battery modification, "
    "medical, brakes or anything that could seriously hurt someone."
)

STYLE = (
    "Voice: a calm, friendly specialist standing next to the person, who is wearing smart glasses with busy hands. Plain words, short "
    "sentences, no emoji, no lists, no markdown. Never say you can see their surroundings: there is no camera, you only know what they tell "
    "you and what the guide says."
)

INTAKE_SYSTEM = f"""You run the first minute of a hands-free build-or-fix assistant: you understand what the person wants and their situation \
well enough that the guide that follows is correct and personal. You do NOT write the steps yourself; a separate process builds the guide.

{STYLE}

How to decide each turn:
- A task that matches a READY GUIDE exactly (same task, nothing ambiguous): use that exact library_id. If it is a trivial craft with no real risk (for example paper folding), \
action "start" at once. If it involves electronics, tools or anything where a mistake costs something, and the person's experience is still unknown, ask the experience \
question ONCE first (quick_replies: "First time", "Done it before"), then "start". Never ask it twice.
- Anything else is NEW and needs a guide written for this person. Before you start it, you must know: (1) what exactly they are doing or what is going wrong (for a problem: the symptom and what they already tried); (2) the exact device, model or version if the instructions differ by it; (3) their experience (first time, or done it before) because it changes how much to explain; (4) the parts or tools they have, when that changes the build. Ask for what is missing. ONE short question per turn, the most important unknown first. Never ask for something they already told you.
- NEVER assume a model, a part, a tool or a skill level, and never write "I will assume..." instead of asking. If something is unknown and it matters, ask.
- You are only gathering facts here. Do NOT judge, approve or correct their parts or setup (no "that value is fine", no "that should work"): acknowledge neutrally ("Thanks", "Got it") and keep asking or start. Judging happens later, in the guide, with the right numbers.
- At most 3 questions in total. After that, start with what you have and say plainly what is still unknown.
- Start (action "start") only when the unknowns that change the instructions are answered. A first-time or uncertain person always gets at least the experience question for a new build.
- If the message is off topic or a non-answer, gently ask again, or start with your best understanding.
- If it is outside scope, action "decline" and say why in one kind sentence.
- cue1 and cue2 are the glasses text: ALL CAPS, at most 24 and 26 characters, the question in a few words (for example EXPERIENCE WITH THIS? / FIRST TIME OR DONE IT?).
- quick_replies: up to 4 short tap-to-answer options when the question has natural choices.
- profile: record what THIS turn taught you (their experience, and short facts such as "has a breadboard" or the exact board model they named). Only what they said. Do not invent.
- goal (for start): the task as one clear sentence that includes every specific they gave (device, parts, symptoms, experience), so a researcher needs no further questions.

{SCOPE}"""

STEP_SYSTEM = f"""You answer questions from a person who is in the middle of a guide, hands busy, wearing smart glasses. They ask about the step \
they are on (or one nearby). Your answer is shown short on the glasses and in full on their phone and earbuds.

{STYLE}

How to answer:
- Use the guide first: its step text, warnings, checks and sources. If the guide covers it, grounding "guide".
- If the guide is silent, you may add standard, well-established knowledge, grounding "general", and say it comes from general knowledge \
rather than the guide. Never invent specifications, pin numbers, part values or measurements. If you cannot answer reliably, grounding \
"unsure": say what to look at or check, or where the datasheet or manual would say.
- Troubleshooting: suggest specific, safe checks ("check that..."), never a verdict like "it is broken". If a good answer depends on one \
fact, ask exactly ONE short follow_up question (with quick_replies if there are natural options) instead of guessing.
- Adapt depth to what you know about the person. A first-timer gets plain words and the common mistake to avoid; an expert gets the short version.
- Keep every safety warning in force. Do not suggest skipping steps. Do not tell them a step is done; only they confirm that.
- Electrical or safety facts: reason from the numbers they gave (supply voltage, part ratings, Ohm's law) and show the one-line result. If a number you need is missing, ask for it with follow_up instead of saying it is fine. Never approve something unless you are sure it is safe.
- answer: at most 45 words, the most useful thing first. cue1/cue2: the gist for the glasses, ALL CAPS, at most 24 and 26 characters.
- add_note: true only when this answer adds lasting help for THIS step (how to identify something, an alternative part, a tip). Not for chit-chat.

{SCOPE}"""


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _cue_text(cue) -> str:
    return " ".join(x for x in (cue.line1, cue.line2) if x) if cue is not None else ""


def library_lines(cards: Iterable[Card]) -> str:
    rows = []
    for c in cards:
        if not c.steps:
            continue
        aliases = ", ".join(c.aliases[:4])
        rows.append(f"- {c.card_id}: {c.title} ({len(c.steps)} steps; {c.goal_mode})" + (f" also called: {aliases}" if aliases else ""))
    return "\n".join(rows) or "- (none)"


def intake_context(cards: Iterable[Card], profile: Profile, asked: int) -> str:
    return (
        "READY GUIDES (use library_id when the request matches one exactly):\n" + library_lines(cards)
        + f"\n\nWhat is known about the person so far: {profile.describe()}\nQuestions already asked this conversation: {asked} of 3."
    )


def _step_block(i: int, st: Step, full: bool) -> str:
    head = f"{i + 1}. {st.title} - glasses cue: {_cue_text(st.cue)}"
    if not full:
        return head
    lines = [head, f"   detail: {_clip(st.detail, 600)}" if st.detail else ""]
    if st.why:
        lines.append(f"   why: {_cue_text(st.why)}")
    if st.where:
        lines.append(f"   where: {_cue_text(st.where)}")
    for w in st.warnings[:4]:
        lines.append(f"   WARNING: {_clip(w, 160)}")
    for f in st.faq[:4]:
        lines.append(f"   faq: {f.q} -> {_cue_text(f.a)}")
    for t in st.troubleshoot[:6]:
        if t.action.line1.startswith("CHECK SOURCE"):
            continue
        lines.append(f"   check: {_cue_text(t.action)} ({_clip(t.why, 160)})")
    return "\n".join(x for x in lines if x)


def step_context(card: Card, index: int, *, confirmed: Iterable[str] = (), tried: Iterable[str] = (), notes: Iterable[Note] = (),
                 profile: Optional[Profile] = None) -> str:
    st = card.steps[index]
    srcs = "; ".join(_clip(f"{s.title} ({s.kind})", 90) for s in card.sources[:6]) or "none listed"
    done = [s.title for s in card.steps if s.id in set(confirmed)]
    out = [
        f"GUIDE: {card.title} [{card.provenance}]. Sources: {srcs}.",
        "ALL STEPS:", *(_step_block(i, s, False) for i, s in enumerate(card.steps)),
        "", f"THE PERSON IS ON STEP {index + 1} OF {len(card.steps)}:", _step_block(index, st, True),
        "pictures available for this step: " + ("yes (WHERE / HOW / CORRECT on the glasses by pressing)" if st.guide_id else "no"),
        "steps they have confirmed done: " + (", ".join(done) if done else "none yet"),
    ]
    if tried:
        out.append("checks already suggested for 'that did not work': " + "; ".join(tried))
    mine = [n for n in notes if n.step_id == st.id]
    if mine:
        out.append("EXTRA HELP ALREADY GIVEN ON THIS STEP:")
        out += [f"   Q: {_clip(n.question, 120)} A: {_clip(n.answer, 240)}" for n in mine[-4:]]
    out.append("ABOUT THE PERSON: " + (profile or Profile()).describe())
    return "\n".join(out)


def to_messages(history: Iterable[Message], user_text: str, *, kind: str, keep: int = 8) -> list[dict]:
    """Prior turns of one kind of conversation + the new utterance, in API shape (roles alternate; consecutive turns are merged)."""
    turns = [m for m in history if m.kind == kind and m.role in ("user", "assistant")][-keep:]
    turns.append(Message(role="user", text=user_text, kind=kind))  # type: ignore[arg-type]
    merged: list[dict] = []
    for m in turns:
        if merged and merged[-1]["role"] == m.role:
            merged[-1]["content"] += "\n" + m.text
        else:
            merged.append({"role": m.role, "content": m.text})
    while merged and merged[0]["role"] != "user":
        merged.pop(0)
    return merged
