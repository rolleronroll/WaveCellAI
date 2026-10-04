import asyncio

from src.rag.prompts import SYSTEM_SMS, build_user_prompt
from src.router import GeminiLLM


async def main() -> None:
    ctx = "[1] Cox's Bazar See: Long sandy beach on the Bay of Bengal. Sunrise and sunset are the best times to visit."
    res = await GeminiLLM().generate(
        SYSTEM_SMS, build_user_prompt("any beaches in cox's bazar?", ctx), max_tokens=1024
    )
    print(repr(res.text))
    print("finish:", res.finish_reason, "| thinking tokens:", res.thought_tokens)


asyncio.run(main())

# import asyncio
#
# from src.analysis import classify
# from src.config import get_settings
# from src.deps import get_router, get_store
# from src.rag import retrieve
# from src.router import ClaudeClient, LLMError, Router
#
# PHONE = "+8801712345678"
#
#
# class BrokenSmall:
#     """Simulates a Gemini outage."""
#
#     async def generate(self, *args, **kwargs):
#         raise LLMError("simulated outage")
#
#
# async def ask(router: Router, question: str, **kwargs) -> None:
#     store = get_store()
#     c = classify(question)
#     ret = await retrieve(store, c.intent, question, phone=PHONE)
#     ans = await router.answer(c.intent, question, ret, **kwargs)
#     print(f"\n> {question}")
#     print(f"  tier={ans.tier} escalated={ans.escalated} conf={ans.confidence} model={ans.model}")
#     print(f"  reason: {ans.reason}")
#     print(f"  reply ({len(ans.text)} chars): {ans.text}")
#
#
# async def main() -> None:
#     router = get_router()
#     for q in [
#         "where can I exchange money",
#         "any beaches in cox's bazar?",
#         "best time to see tigers in the sundarbans",
#         "bus from dhaka to cox bazar after 08:00",
#         "SOS I was robbed",
#         "???",
#     ]:
#         await ask(router, q)
#
#     print("\n--- simulated Gemini outage: should fall back to Claude ---")
#     broken = Router(BrokenSmall(), ClaudeClient(), get_settings())
#     await ask(broken, "where can I exchange money")
#
#     print("\n--- Claude not allowed: should return the static message ---")
#     await ask(broken, "where can I exchange money", allow_claude=False)
#
#
# asyncio.run(main())