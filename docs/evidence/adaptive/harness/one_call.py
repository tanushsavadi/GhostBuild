import os, time, traceback
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path.cwd() / ".env", override=False)
from ghostbuild_core.assistant import prompts
from ghostbuild_core.assistant.brain import AnthropicBrain
from ghostbuild_core.assistant.schemas import IntakeWire as IntakeReply, Profile
import anthropic; b = AnthropicBrain(client=anthropic.Anthropic(timeout=90, max_retries=0))
system = prompts.INTAKE_SYSTEM + "\n\n" + prompts.intake_context([], Profile(), 0)
msgs = [{"role": "user", "content": "fix my bike tyre"}]
t = time.monotonic()
try:
    r = b._parse(system, msgs, IntakeReply, b.fast)
    print("ok", int((time.monotonic()-t)*1000), "ms stop=", r.stop_reason, "usage out=", r.usage.output_tokens, "speed=", getattr(r.usage, "speed", None))
    print(r.parsed_output.model_dump_json()[:1500])
except Exception as e:
    print("ERR", int((time.monotonic()-t)*1000), "ms", type(e).__name__, str(e)[:800])
