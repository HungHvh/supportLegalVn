import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
url = "https://api.groq.com/openai/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "llama-3.1-8b-instant", # Use a smaller one first
    "messages": [{"role": "user", "content": "Hi"}],
    "stream": False
}

try:
    print(f"Testing URL: {url}")
    response = httpx.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
    else:
        print("Success!")
        print(response.json()["choices"][0]["message"]["content"])
except Exception as e:
    print(f"Error: {e}")
