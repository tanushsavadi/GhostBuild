# /// script
# requires-python = ">=3.10"
# ///
"""Build g2/src/asllex.json: one card per ASL-LEX 2.0 sign, for every word the
hand-checked deck (g2/src/deck.json) does not cover.

Each card's two how-to lines are composed mechanically from the sign's
ASL-LEX 2.0 phonology coding (handshape, sign type, location, movement), so
nothing is invented, but the wording is a template and every card is
UNCHECKED. The handshape descriptions below were drafted by AI (Claude) from
the ASL-LEX drawings. Data: ASL-LEX 2.0 (asl-lex.org), CC BY-NC 4.0.

Run (from the repo root):  uv run tools/build_deck.py
The source JSON is cached in tmp/ (git-ignored).
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = "https://asl-lex.org/visualization/data/sign_props.json"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tmp" / "asllex_sign_props.json"
OUT = ROOT / "g2" / "src" / "asllex.json"
HOWTO = ROOT / "tools" / "howto.json"
TOP = ROOT / "g2" / "src" / "top.json"
TOP_N = 100

HANDSHAPE = {
    "1": "Index finger up", "3": "Thumb, index, middle out", "4": "4 fingers up, thumb in",
    "5": "Open hand, fingers spread", "7": "Ring finger touches thumb", "8": "Middle finger touches thumb",
    "a": "Fist, thumb at the side", "b": "Flat hand", "baby_o": "Index tip on thumb tip",
    "bent_1": "Index finger bent", "bent_l": "Thumb out, index bent", "bent_v": "Index and middle bent",
    "c": "Hand curved like a C", "closed_b": "Flat hand, thumb tucked", "closed_e": "Fingertips curled tight",
    "curved_1": "Index finger hooked", "curved_4": "4 fingers curved", "curved_5": "Claw: fingers spread, bent",
    "curved_h": "2 fingers together, curved", "curved_l": "Thumb and index curved", "curved_v": "2 fingers apart, curved",
    "d": "Index up, others touch thumb", "e": "Fingertips curled onto thumb", "f": "Index touches thumb, 3 up",
    "flat_1": "Index pointing sideways", "flat_4": "4 fingers bent at the base", "flat_b": "Flat fingers bent at base",
    "flat_h": "Index, middle and thumb out", "flat_horns": "Index and pinky bent flat", "flat_ily": "Thumb, index, pinky bent",
    "flat_m": "3 fingers bent over thumb", "flat_n": "2 fingers bent over thumb", "flat_o": "Flat fingertips on thumb",
    "flat_v": "2 fingers apart, bent at base", "flatspread_5": "Spread fingers bent at base", "g": "Index and thumb sideways",
    "goody_goody": "Special handshape", "h": "Index and middle together", "horns": "Index and pinky up",
    "i": "Pinky up", "ily": "Thumb, index, pinky out", "k": "Index, middle up, thumb between",
    "l": "Index up, thumb out", "o": "Fingertips touch thumb, round", "open_8": "Spread hand, middle bent",
    "open_b": "Flat hand, thumb out", "open_e": "Fingers bent, near thumb", "open_f": "Index on thumb, 3 spread",
    "open_h": "Index and middle out, thumb out", "p": "K shape, pointing down", "r": "Middle crossed over index",
    "s": "Fist, thumb across", "spread_e": "Fingertips curled, spread", "spread_open_e": "Fingers bent, spread",
    "stacked_5": "Fingers fanned out", "t": "Thumb between index, middle", "v": "Index and middle apart",
    "w": "3 fingers up, apart", "y": "Thumb and pinky out",
}

LOCATION = {
    "Neutral": "In front of you", "Palm": "On other palm", "HeadAway": "Near your head", "Mouth": "At mouth",
    "Forehead": "At forehead", "Chin": "At chin", "CheekNose": "At cheek", "HandAway": "Near other hand",
    "FingerRadial": "On other hand's index side", "TorsoTop": "On upper chest", "PalmBack": "On back of other hand",
    "FingerTip": "At other fingertips", "FingerBack": "On back of other fingers", "Clavicle": "At collarbone",
    "BodyAway": "In front of body", "Eye": "Near eye", "FingerFront": "On other fingers",
    "Shoulder": "At shoulder", "FingerUlnar": "On other hand's pinky side", "UnderChin": "Under chin",
    "Neck": "At neck", "ForearmUlnar": "On forearm", "TorsoMid": "At middle of chest", "ArmAway": "Near arm",
    "Heel": "On heel of other hand", "UpperArm": "On upper arm", "HeadTop": "On top of head", "Hips": "At hips",
    "WristBack": "On back of wrist", "TorsoBottom": "At stomach", "ForearmBack": "On forearm",
    "UpperLip": "At upper lip", "Waist": "At waist", "WristFront": "On inside of wrist",
    "ElbowBack": "At elbow", "ForearmFront": "On forearm", "Other": "Location: see video",
}

MOVEMENT = {
    "Straight": "move straight", "Curved": "move in an arc", "Circular": "circle",
    "BackAndForth": "back and forth", "Z-shaped": "zigzag", "X-shaped": "cross",
    "Other": "move (see video)",
}

# Common English words whose usual ASL sign is filed under another entry.
ALIASES = {
    "i": "me", "he": "this/it", "she": "this/it", "it": "this/it", "this": "this/it", "that": "this/it",
    "goodbye": "bye", "okay": "fine_2", "ok": "fine_2", "food": "eat_1",
    "mom": "mother", "dad": "father",
}


def load() -> list[dict]:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as res:
            CACHE.write_bytes(res.read())
    return json.loads(CACHE.read_text(encoding="utf-8"))


def hands_line(e: dict) -> str:
    hs = HANDSHAPE.get(e.get("Handshape.2.0") or "", "Handshape: see video")
    kind = e.get("SignType.2.0") or ""
    if kind in ("SymmetricalOrAlternating", "AsymmetricalSameHandshape", "DominanceViolation", "SymmetryViolation"):
        return f"Both hands: {hs.lower()}"
    if kind == "AsymmetricalDifferentHandshape":
        nd = str(e.get("NonDominantHandshape.2.0") or "").lower()
        return f"{hs}; other: {HANDSHAPE.get(nd, 'see video').lower()}"
    return hs


def motion_line(e: dict) -> str:
    where = LOCATION.get(e.get("MinorLocation.2.0") or "", "In front of you")
    move = e.get("Movement.2.0") or "None"
    if move == "None":
        what = "change handshape" if e.get("FlexionChange.2.0") else "hold"
    else:
        what = MOVEMENT.get(move, "move")
        if e.get("FlexionChange.2.0"):
            what += ", fingers bend"
    second = e.get("SecondMinorLocation.2.0") or ""
    if second.endswith("Away") and move != "None":
        what += " away"
    if e.get("RepeatedMovement.2.0"):
        what += ", repeat"
    return f"{where}, {what}"


def words_for(entry_id: str) -> list[str]:
    if "/" in entry_id:
        return [w for w in entry_id.split("/") if w.isalpha()]
    base = re.sub(r"_\d+$", "", entry_id)
    return [base.replace("_", " ").lower()]


def main() -> None:
    entries = load()
    by_id = {e["EntryID"]: e for e in entries}
    freq = lambda e: e.get("SignFrequency(M)") or 0.0  # noqa: E731

    # One sign per word: the most frequent variant (e.g. deaf_1 vs deaf_2).
    best: dict[str, dict] = {}
    for e in entries:
        for w in words_for(e["EntryID"]):
            if w and (w not in best or freq(e) > freq(best[w])):
                best[w] = e
    for word, entry_id in ALIASES.items():
        best[word] = by_id[entry_id]

    howto = {k: v for k, v in json.loads(HOWTO.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    for word, lines in howto.items():
        if word not in best:
            raise SystemExit(f"howto.json: '{word}' is not an ASL-LEX word")
        # [line 1, line 2] or [line 1, line 2, handshape id] to use a different drawing.
        if len(lines) not in (2, 3) or any(len(line) > 36 for line in lines[:2]):
            raise SystemExit(f"howto.json: '{word}' needs 2 lines of at most 36 characters")
        if len(lines) == 3 and not (ROOT / "g2" / "public" / "handshapes" / f"{lines[2]}_bold.png").exists():
            raise SystemExit(f"howto.json: '{word}' names handshape '{lines[2]}', which has no drawing")

    # Lines belong to the sign, so every word mapped to it (I -> ME, food -> EAT) gets them.
    howto_by_entry = {best[w]["EntryID"]: lines for w, lines in howto.items()}

    out = {}
    for word, e in sorted(best.items()):
        # "this/it" is the pointing sign used for he, she, it, this and that.
        gloss = "POINT" if "/" in e["EntryID"] else re.sub(r"_\d+$", "", e["EntryID"]).replace("_", "-").upper()
        video = (e.get("VimeoVideo") or "").rsplit("/", 1)[-1]
        # Last field: 1 = hand-written lines from howto.json, 0 = template lines.
        if e["EntryID"] in howto_by_entry:
            lines = howto_by_entry[e["EntryID"]]
            handshape = lines[2] if len(lines) == 3 else e.get("Handshape.2.0")
            out[word] = [gloss, handshape, lines[0], lines[1], video, 1]
        else:
            out[word] = [gloss, e.get("Handshape.2.0"), hands_line(e), motion_line(e), video, 0]

    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(out)} words to {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")

    # The most-used signs (ASL-LEX frequency rating), one word per sign, for review mode.
    word_for = {}
    for word, e in best.items():
        base = re.sub(r"_\d+$", "", e["EntryID"]).replace("_", " ").lower()
        if e["EntryID"] not in word_for or word == base:
            word_for[e["EntryID"]] = word
    ranked = sorted(word_for, key=lambda eid: -freq(by_id[eid]))
    top = [word_for[eid] for eid in ranked if word_for[eid].replace(" ", "").isalpha()][:TOP_N]
    TOP.write_text(json.dumps(top, indent=0), encoding="utf-8")
    print(f"wrote the {len(top)} most-used signs to {TOP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
