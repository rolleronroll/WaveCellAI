import asyncio

from src.analysis import classify
from src.deps import get_store
from src.rag import retrieve

TESTS = [
    "bus from dhaka to cox bazar after 08:00",
    "SOS I was robbed",
    "any beaches in cox's bazar?",
    "where can I exchange money",
    "talk to a human",
    "bachao",
]


async def main() -> None:
    store = get_store()
    for q in TESTS:
        r = classify(q)
        out = await retrieve(store, r.intent, q, phone="+8801712345678")
        print(f"{q!r}")
        print(f"  intent={r.intent} ({r.reason}) top_score={out.top_score:.2f}")
        print(f"  direct={out.direct_answer}")
        print(f"  context={out.context[:90]!r}")


asyncio.run(main())