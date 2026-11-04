import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

meta = OpenAI(
    api_key=os.environ["META_API_KEY"],
    base_url=os.getenv("META_BASE_URL", "https://api.meta.ai/v1"),
)
fireworks = OpenAI(
    api_key=os.environ["FIREWORKS_API_KEY"],
    base_url="https://api.fireworks.ai/inference/v1",
)

TESTS = [
    ("Muse Spark (agent + juror 1)", meta, "muse-spark-1.3"),
    ("Muse Wonder (escalation)", meta, "muse-wonder-1.0"),
    ("Muse Spark Open (juror 2)", fireworks, "accounts/fireworks/models/muse-spark-open"),
]

PROMPT = "Reply with exactly one word: ready"

for label, client, model in TESTS:
    start = time.time()
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=400,
        )
        text = (r.choices[0].message.content or "").strip()
        u = r.usage
        print(f"OK   {label:30} {time.time() - start:5.1f}s  "
              f"tokens in/out {u.prompt_tokens}/{u.completion_tokens}  -> {text[:40]!r}")
    except Exception as e:
        print(f"FAIL {label:30} {type(e).__name__}: {e}")