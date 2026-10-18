"""MOCK shapes only. NOT real CREAO output.

The real CREAO run response has never been seen by this repo (no API key yet). These are two realistic-but-invented shapes a
general research agent might return, written for NON-Raspberry-Pi tasks so the tests prove the normalizer is not hard-coded:

  MOCK_A_ENVELOPE_RUN  the agent returns something close to our own envelope (card + research), nested under data.output
  MOCK_B_FENCED_RUN    the agent answers in prose with a fenced ```json block inside a chat-style message list

Every URL below is an illustrative example, not a fetched source.
"""

from __future__ import annotations

import json

MOCK_A_REQUEST = "replace a bicycle inner tube"

MOCK_A_ENVELOPE_RUN = {
    "id": "run_mock_bike_01",
    "status": "Completed",
    "data": {
        "output": {
            "run_id": "run_mock_bike_01",
            "request": MOCK_A_REQUEST,
            "card": {
                "v": 2,
                "card_id": "replace_bicycle_inner_tube",
                "title": "Replace a bicycle inner tube",
                "provenance": "AUTHORED DEMO METADATA",  # an agent copying the example: the normalizer must not trust this
                "sources": [
                    {"id": "yt_tube", "kind": "VIDEO TUTORIAL", "title": "MOCK: fixing a flat, video", "url": "https://www.youtube.com/watch?v=MOCKvideo01", "file": None},
                    {"id": "shop_docs", "kind": "WEB TUTORIAL", "title": "MOCK: bike shop flat repair page", "url": "https://bikeshop.example.com/repair/flat-tire", "file": None},
                ],
                "tests": [],
                "steps": [
                    {
                        "id": "wheel_off", "title": "Remove the wheel",
                        "cue": {"line1": "REMOVE THE WHEEL", "line2": "RELEASE BRAKE FIRST"},
                        "detail": "Open the quick release or loosen the axle nuts, then lift the wheel out of the frame.",
                        "why": None, "where": None, "warnings": ["Release the brake first so the tyre clears the pads."],
                        "faq": [], "troubleshoot": [
                            {"when": [], "action": {"line1": "CHECK BRAKE RELEASE", "line2": ""}, "why": "The wheel will not drop out while the brake is clamped.",
                             "cites": [{"source": "yt_tube", "loc": "t=00:01:05", "quote": None, "url": "https://www.youtube.com/watch?v=MOCKvideo01&t=65s"}], "guide_id": None}],
                        "guide_id": None, "verify": None, "requires": [],
                    },
                    {
                        "id": "tyre_off", "title": "Take one tyre side off",
                        "cue": {"line1": "LEVER ONE TYRE SIDE", "line2": "OFF THE RIM"},
                        "detail": "Seat a tyre lever under the bead and hook it on a spoke; slide the second lever around.",
                        "why": {"line1": "UNCERTAIN: LEVER SIZE", "line2": "SOURCES DISAGREE"}, "where": None, "warnings": [],
                        "faq": [{"q": "do i need tyre levers", "a": {"line1": "YES, TWO LEVERS", "line2": "HELP A LOT"}}],
                        "troubleshoot": [
                            {"when": [], "action": {"line1": "CHECK BEAD IN RIM WELL", "line2": ""}, "why": "A bead out of the well is tight.",
                             "cites": [{"source": "yt_tube", "loc": "t=00:02:15", "quote": None, "url": "https://www.youtube.com/watch?v=MOCKvideo01&t=135s"}], "guide_id": None}],
                        "guide_id": None, "verify": None, "requires": ["wheel_off"],
                    },
                    {
                        "id": "tube_in", "title": "Fit the new tube",
                        "cue": {"line1": "FIT THE NEW TUBE", "line2": "PUMP A LITTLE AIR"},
                        "detail": "Add a little air so the tube holds its shape, then tuck the valve through the hole.",
                        "why": None, "where": None, "warnings": [], "faq": [], "troubleshoot": [], "guide_id": None, "verify": None, "requires": ["tyre_off"],
                    },
                ],
                "functional": None,
                "guides": [],
                "goal_mode": "fix",
                "aliases": ["replace a bicycle inner tube", "bike flat tire"],
            },
            "source_texts": {},
            "research": {
                "sources": [
                    {"id": "yt_tube", "kind": "video", "url": "https://www.youtube.com/watch?v=MOCKvideo01", "used_for": "technique and timing"},
                    {"id": "shop_docs", "kind": "tutorial", "url": "https://bikeshop.example.com/repair/flat-tire", "used_for": "tool list"},
                ],
                "video_notes": [{"url": "https://www.youtube.com/watch?v=MOCKvideo01&t=135s", "t_start": "00:02:15", "t_end": "00:03:05", "summary": "levering the first tyre side off"}],
                "visual_references": [{"view": "how", "url": "", "description": "a close shot of the lever hooked on a spoke"}],
                "uncertainties": ["Only the transcript and page text were read; video frames were NOT inspected.", "Sources disagree on how many levers to use."],
            },
        }
    },
}

MOCK_B_REQUEST = "reset a home router to factory settings"

_MOCK_B_PLAYBOOK = {
    "title": "Reset a home router to factory settings",
    "goal": "Return the router to its factory defaults",
    "device": "home wifi router",
    "intent": "fix",
    "safety": ["Resetting erases your Wi-Fi name, password and any custom settings; note them first."],
    "steps": [
        {"title": "Note your current settings", "instruction": "Write down the Wi-Fi name and password and any custom DNS because they are erased by the reset."},
        {"title": "Find the reset hole", "instruction": "Look on the back panel for a small recessed hole labelled RESET.", "where": "Back panel"},
        {"title": "Power the router on", "instruction": "Plug the power adapter in and wait until the power light is steady (about two minutes).",
         "why": "A reset while the unit is still booting may not register."},
        {"title": "Hold the reset button", "instruction": "Press and hold the recessed button with a straightened paperclip for 10 to 15 seconds (some models need 30), then release when the lights flash.",
         "description": "Do not let go early or the reset will not complete.", "tips": ["Use a paperclip, never a sharp pin that could snap off inside."],
         "visual": {"description": "Photo of a paperclip pressing the recessed reset hole", "url": "https://www.ifixit.com/Guide/MOCK-Reset-A-Router/000000"}},
        {"title": "Wait for the restart", "action": "Wait about three minutes while the router restarts and the lights settle; the case may be warm.", "timestamp": "00:04:20", "source": "https://www.youtube.com/watch?v=MOCKrouter02"},
        {"title": "Sign in with the defaults", "action": "Connect to the default Wi-Fi name printed on the label and sign in with the default admin password from the label."},
    ],
    "sources": [
        {"title": "MOCK: router reset guide", "url": "https://www.ifixit.com/Guide/MOCK-Reset-A-Router/000000", "used_for": "button location and hold time"},
        {"title": "MOCK: reset walkthrough video", "url": "https://www.youtube.com/watch?v=MOCKrouter02", "timestamps": [{"t": "00:04:20", "note": "wait for restart"}]},
        {"title": "MOCK: vendor forum thread", "url": "https://forum.example.org/threads/router-reset-hold-time"},
    ],
    "faq": [{"question": "How long do I hold the reset button?", "answer": "Ten to fifteen seconds on most models."}],
    "troubleshooting": [{"problem": "The lights do not flash after holding", "fix": "Check that the router has power and hold the button a little longer."}],
    "uncertainties": [
        "Hold time differs by model; the sources say 10, 15 or 30 seconds.",
        "Step 4: only text was read, so the exact light pattern that signals the reset was NOT seen.",
        "Photos and video frames were not inspected.",
    ],
    "images": ["Annotated diagram of a router back panel with the reset hole circled"],
}

MOCK_B_FENCED_RUN = {
    "run_id": "run_mock_router_02",
    "state": "COMPLETED",
    "messages": [
        {"role": "user", "content": MOCK_B_REQUEST},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Here is the playbook I compiled from the three sources.\n\n```json\n" + json.dumps(_MOCK_B_PLAYBOOK, indent=2) + "\n```\n\nLet me know if you want a follow-up."}
        ]},
    ],
}
