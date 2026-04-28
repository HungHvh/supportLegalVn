import asyncio
import os
from core.classifier import LegalQueryClassifier
from tools.groq_client import GroqClient
from dotenv import load_dotenv
from unittest.mock import patch

load_dotenv()

async def test_groq_fallback():
    print("--- Testing Groq Fallback to Gemini ---")
    classifier = LegalQueryClassifier(provider="groq", fallback_provider="gemini")
    
    # Mock GroqClient to fail
    with patch.object(GroqClient, 'generate_content_async', side_effect=Exception("Groq Simulated Failure")):
        query = "Vợ chồng ly hôn thì tài sản chung chia thế nào?"
        print(f"Query: {query}")
        
        try:
            result = await classifier.classify(query)
            print(f"Result: {result}")
            print(f"Domains: {result.domains}")
            # If it returns a result instead of re-raising, it fell back.
            # (Assuming Gemini is working or it returns a safe fallback)
        except Exception as e:
            print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_groq_fallback())
