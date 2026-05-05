import requests
import json

def test_stream():
    url = "http://localhost:8000/api/v1/stream"
    payload = {
        "query": "Tội trộm cắp tài sản bị xử lý như thế nào?",
        "chat_history": []
    }
    
    print(f"Connecting to {url}...")
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        print("Stream started. Received events:")
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data = json.loads(decoded_line[6:])
                    event_type = data.get("type")
                    print(f"  - Event: {event_type}")
                    if event_type == "citations":
                        print(f"    [Citations found: {len(data.get('data', []))}]")
                    elif event_type == "classification":
                        print(f"    [Domains: {data.get('domains')}]")
                    elif event_type == "done":
                        print("Stream finished successfully.")
                        break
    except Exception as e:
        print(f"Error during streaming test: {e}")

if __name__ == "__main__":
    test_stream()
