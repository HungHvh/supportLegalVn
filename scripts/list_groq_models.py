import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
headers = {"Authorization": f"Bearer {api_key}"}

try:
    response = httpx.get("https://api.groq.com/openai/v1/models", headers=headers)
    response.raise_for_status()
    models = response.json()
    
    print("Available Groq Models:")
    for model in models["data"]:
        print(f"- {model['id']}")
except Exception as e:
    print(f"Error: {e}")
