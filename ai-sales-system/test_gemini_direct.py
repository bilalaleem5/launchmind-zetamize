import requests, json
from config import GEMINI_KEYS

def test_gemini():
    key = GEMINI_KEYS[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    body = {
        "contents": [{"role": "user", "parts": [{"text": "Hello, are you working?"}]}],
    }
    r = requests.post(url, json=body, timeout=30)
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.text}")

if __name__ == "__main__":
    test_gemini()
