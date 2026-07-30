import asyncio
from openai import AsyncOpenAI

async def main():
    client = AsyncOpenAI(api_key="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", base_url="https://integrate.api.nvidia.com/v1")
    try:
        models = await client.models.list()
        for m in models.data:
            print(m.id)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
