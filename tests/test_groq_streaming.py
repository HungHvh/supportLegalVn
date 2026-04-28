import asyncio
import os
from dotenv import load_dotenv
from tools.groq_client import GroqClient

import pytest

load_dotenv()

@pytest.mark.asyncio
async def test_groq_streaming():
    """Smoke test to verify Groq streaming works."""
    client = GroqClient(model_name="llama-3.1-8b-instant")
    prompt = "Xin chào, hãy giới thiệu ngắn gọn về bản thân bạn."
    
    print(f"\nTesting Groq Streaming with model: {client.model_name}")
    print("-" * 30)
    
    try:
        tokens = []
        async for chunk in client.astream_query(prompt):
            if chunk.text:
                print(chunk.text, end="", flush=True)
                tokens.append(chunk.text)
        
        print("\n" + "-" * 30)
        assert len(tokens) > 0
        print(f"[OK] Received {len(tokens)} chunks.")
    except Exception as e:
        print(f"\n[FAIL] Streaming failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_groq_streaming())
