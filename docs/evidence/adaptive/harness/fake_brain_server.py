"""QA harness: the real GhostBuild app with a clearly-labelled delayed FakeBrain (no paid calls). Not a demo backend."""
import os, sys
from pathlib import Path
for k in ("ANTHROPIC_API_KEY", "CREAO_API_KEY", "ELEVENLABS_API_KEY"):
    os.environ[k] = ""
os.environ.update(GB_CREAO="0", GB_LIVE_RESEARCH="0", GB_VOICE="0", GB_TTS="0", GB_DISCOVERY_LIVE="0")
import uvicorn
from ghostbuild_core.assistant.brain import FakeBrain
from ghostbuild_core.assistant.schemas import StepReply
from ghostbuild_core.cards import load_cards
from ghostbuild_core.runtime import Runtime
from ghostbuild_core.server import create_app
from integrations.product_discovery import attach_discovery

LONG = ("[FAKE BRAIN, QA ONLY] Cam locks pull two panels together. Push each round lock into its hole with the arrow "
        "pointing at the bolt, so the slot faces the edge where the cam bolt will enter. Then turn it clockwise about a quarter "
        "of a turn with a flat or Phillips screwdriver until you feel it bite; do not keep turning or you can strip the chipboard. "
        "If the lock spins freely, the bolt is not seated: back it out, check the bolt is fully screwed into the other panel, and try again. "
        "This answer is long on purpose so the glasses must show several pages; the last words are END OF ANSWER.")
def reply(_m):
    return StepReply(answer=LONG, cue1="CAM LOCKS PULL PANELS", cue2="TURN A QUARTER TURN", grounding="general")
port = int(sys.argv[1]); log_dir = sys.argv[2]
rt = Runtime(load_cards("knowledge/cards"), log_dir=log_dir, asset_root=Path("."), require_device_link=True,
             brain=FakeBrain(step=[reply] * 50, delay_s=1.5))
attach_discovery(rt)
uvicorn.run(create_app(rt), host="0.0.0.0", port=port, log_level="warning")
