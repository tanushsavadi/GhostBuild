"""Pure builders for what a brain is told. No IO. Everything the model sees is assembled here so it can be reviewed and tested."""

from __future__ import annotations

from typing import Iterable, Optional

from contracts.models import Card, Step

from .schemas import Message, Note, Profile
from ..presentation import instruction

SCOPE = (
    "Scope: any physical build, assembly, repair, setup or troubleshooting a careful non-professional can do from trustworthy "
    "documentation: furniture, devices and computers, appliances, bikes, maker tools, crafts, hobby electronics and similar. "
    "Hazardous work (mains electricity, gas, lithium batteries, brakes or structural safety, anything that could seriously hurt "
    "someone) is only guided with an exact model, an official procedure and its warnings; otherwise decline kindly and suggest a "
    "qualified professional. Medical tasks are always declined."
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
- Describe a ready guide only by its source and kind ("a guide from Park Tool's instructions"); never call it tested, verified or reviewed unless its provenance says HUMAN-REVIEWED.
- Never name or rank a likely cause from a symptom ("usually software", "probably the cable"). Say what you will check first and why it is safe.
- Your objective is MINIMUM SUFFICIENT CONTEXT, not a checklist. Use everything supplied, including multi-sentence replies. Ask ONE highest-value question only if its answer materially changes identity, procedure, diagnosis, tools, branch or safety. Explain its purpose briefly. User experience is relevant only when it changes guidance; do not ask it mechanically.
- Set decision to ASK_QUESTION, IDENTIFY_PRODUCT, RESEARCH, START_GUIDE, CONTINUE_GUIDE, SHOW_VISUAL, EXPLAIN, TROUBLESHOOT, REQUEST_CONFIRMATION or ESCALATE_OR_STOP. Keep legacy action ask/start/decline consistent. START_GUIDE uses an exact sourced library_id only; RESEARCH means context is sufficient to target real sources, not permission to invent steps.
- context_sufficient is true only when every critical model-specific and safety prerequisite for the proposed action is resolved. List exact unresolved requirements in critical_unknowns. Never assume a product model, variant or safe value. Do not start just because several questions have been asked. There is NO fixed question cap. Zero to three is a UX target, not a rule.
- critical_unknowns are only facts the PERSON must supply before research can target the right official source or before it is safe \
to begin (exact identity, an immediate hazard where they are). Anything the official documentation answers (which procedure applies, \
what equipment, parts or kit the model came with, specifications, tool sizes) or a choice between documented procedures is NOT a \
critical unknown: choose RESEARCH, write the open choice into goal ("cover both documented options for ..."), and the guide asks at \
the step where it matters. Take short answers at face value: "both", "yes", "all of them" answer the question you just asked.
- Distinguish confirmed USER facts from INFERRED hypotheses. facts must have field, value, origin and quote. experience and profile_facts record what this turn taught you about the person, from their own words only. A user fact needs an exact quote from accepted user text. Do not turn an inference into a user observation. Update several facts at once when supplied together. goal incorporates confirmed facts only.
- question_key names the particular missing fact; question_reason states why its answer would change the next safe action. Do not ask a resolved fact again. If the user does not know, provide a practical identification method using trusted reference notes or offer available visuals. Use identification_help for that help. Never identify a product or setup from an ambiguous label alone. If it still cannot be identified, state exactly what is missing and stop the affected operation.
- Corrections supersede earlier facts, invalidate mismatched sources/branches, and preserve the person's progress until the correct branch is available. A new goal interrupts the old conversation. Do not carry symptoms or model assumptions from the old goal.
- A ready low-risk guide that matches exactly may begin immediately. Otherwise, critical identity/safety unknowns must be resolved before research or model-specific guidance. Safe sourced preliminary diagnostics may be selected as an exact READY GUIDE while larger research remains pending; no invented disassembly or irreversible actions.
- Brand-specific assembly must go through the existing product-source adapter, confirmation and verified assembly manual. Never select a generic unbox/inventory guide for an unidentified product.
- For an uncertain or unclear transcript that could change a consequential action, use REQUEST_CONFIRMATION. Do not execute from partial speech. Text and push-to-talk remain available.
- Do not repeat a failed question with different words. Offer an identification alternative or ESCALATE_OR_STOP. A missing model can legitimately block a procedure; say so without guessing.
- No steps or repairs in the intake answer. Only clarify, explain a sourced identification method, or select an already sourced guide. Hypotheses are explicitly uncertain and never diagnoses.
- cue1/cue2: ALL CAPS, at most 24/26 characters; quick_replies: up to four natural choices. say: one concise conversational question or useful explanation. branch: the proposed workflow branch, not a physical success claim.

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
- answer: enough detail to answer completely, normally 30-100 words; do not truncate an explanation, the most useful thing first. cue1/cue2: the gist for the glasses, ALL CAPS, at most 24 and 26 characters.
- In a diagnosis, never claim or rank a cause from symptoms or a single check; say what the result suggests and which step comes next in the guide. Answers at a question step may point to its choices.
- decision describes EXPLAIN, SHOW_VISUAL, TROUBLESHOOT, ASK_QUESTION, REQUEST_CONFIRMATION, CONTINUE_GUIDE or ESCALATE_OR_STOP. Never change physical completion from this output. Critical unknowns block model-specific alternatives. For "mine looks different" clarify identity/configuration before further instructions. Missing tools or alternate parts require compatibility evidence, not a guessed substitution. "Already done" cannot establish measured success.
- facts updates the structured task context; user facts require a verbatim quote. Preserve uncertainty. A correction changes applicability, not the historical evidence log.
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
        + f"\n\nWhat is known about the person so far: {profile.describe()}\nQuestions already asked this conversation: {asked}; no fixed cap."
    )


def _step_block(i: int, st: Step, full: bool) -> str:
    kind = "" if st.kind == "action" else f" [{st.kind.upper()}" + (": " + " | ".join(f"{c.label} -> {c.next}" for c in st.choices) if st.choices else "") + "]"
    head = f"{i + 1}. ({st.id}) {st.title} - glasses cue: {_cue_text(instruction(st))}{kind}" + (f" -> next {st.next}" if st.next else "")
    if not full:
        return head
    lines = [head, f"   detail: {_clip(st.detail, 600)}" if st.detail else ""]
    if st.why:
        lines.append(f"   why: {_cue_text(st.why)}")
    if st.where:
        lines.append(f"   where: {_cue_text(st.where)}")
    for p in st.parts:
        lines.append(f"   part {p.id}: qty {p.qty if p.qty is not None else 'not printed'}; {p.name}; avoid={p.avoid}; {p.note or ''}")
    for c in st.cites:
        lines.append(f"   source citation: {c.loc} {c.url or ''}" + (f' quote: "{_clip(c.quote, 200)}"' if c.quote else ""))
    if st.expected:
        lines.append(f"   how to tell it worked (from the source): {_clip(st.expected, 300)}")
    if st.tools:
        lines.append("   tools: " + ", ".join(st.tools[:8]))
    if st.risk != "low":
        lines.append(f"   RISK: {st.risk} (hazard steps need the source's warnings followed exactly; never shortcut them)")
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
                 profile: Optional[Profile] = None, product: Optional[dict] = None, observations: Iterable[str] = ()) -> str:
    st = card.steps[index]
    srcs = "; ".join(_clip(f"{s.title} ({s.kind})", 90) for s in card.sources[:6]) or "none listed"
    done = [s.title for s in card.steps if s.id in set(confirmed)]
    out = [
        f"GUIDE: {card.title} [{card.provenance}]. Sources: {srcs}.",
        "PRODUCT AND CONFIGURATION: " + str(product or "No product selected"),
        "ALL STEPS:", *(_step_block(i, s, False) for i, s in enumerate(card.steps)),
        "", f"THE PERSON IS ON STEP {index + 1} OF {len(card.steps)}:", _step_block(index, st, True),
        "pictures available for this step: " + ("yes (WHERE / HOW / CORRECT on the glasses by pressing)" if st.guide_id else "no"),
        "steps they have confirmed done: " + (", ".join(done) if done else "none yet"),
    ]
    obs = list(observations)
    if obs:
        out.append("WHAT THE PERSON REPORTED AT QUESTION STEPS (their word, not measured): " + "; ".join(obs))
    if card.task_kind:
        out.append(f"TASK KIND: {card.task_kind}. A diagnosis never claims a cause from symptoms; outcomes say what a result suggests.")
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
