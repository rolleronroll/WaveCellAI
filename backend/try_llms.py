import asyncio

from src.router import ClaudeClient, GeminiLLM


async def main() -> None:
    system = "Reply with one short word."
    for name, call in (
        ("gemini", lambda: GeminiLLM().generate(system, "Say hello", max_tokens=256)),
        ("claude", lambda: ClaudeClient().generate(system, "Say hello", max_tokens=64)),
    ):
        try:
            result = await call()
            print(name, "OK:", getattr(result, "text", result))
        except Exception as exc:
            print(name, "FAILED:", type(exc).__name__, exc)


asyncio.run(main())