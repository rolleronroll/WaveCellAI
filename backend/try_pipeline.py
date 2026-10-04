import asyncio

from src.deps import get_pipeline

TESTS = [
    # "cox bazar e beach ache?",
    # "dhaka se cox bazar bus kab hai, 8 baje ke baad",
    # "SOS bachao amar boat dube jacche",
    # "Give me today's tidal news",
    # "launch from Dhaka to Barisal after 20:00?",
    # "is there any signal/high tide today in Cox's Bazar?",
    # "what is today's সংকেত, জোয়ার, ভাটা?",
    # "signal 5",
    "what is the current sea signal in bangladesh",
]


async def main() -> None:
    pipe = get_pipeline()
    for q in TESTS:
        r = await pipe.run("+8801712345678", q)
        print(f"\n> {q}")
        print(f"  lang={r.lang} intent={r.intent} tier={r.tier} septets={r.septets} bytes={r.bytes_used}")
        print(f"  english: {r.english_query}")
        print(f"  reason: {r.reason}")
        print(f"  reply: {r.reply}")


asyncio.run(main())