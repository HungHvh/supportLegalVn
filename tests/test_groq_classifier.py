import asyncio
import os
from core.classifier import LegalQueryClassifier
from dotenv import load_dotenv

load_dotenv()

async def test_groq_classifier():
    print("--- Testing Groq Classifier ---")
    classifier = LegalQueryClassifier()
    
    query = "Vợ chồng ly hôn thì tài sản chung chia thế nào?"
    print(f"Query: {query}")
    
    try:
        result = await classifier.classify(query)
        print(f"Result: {result}")
        print(f"Domains: {result.domains}")
        print(f"Confidence: {result.confidence}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_groq_classifier())
