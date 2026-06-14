import os
from dotenv import load_dotenv
import httpx

load_dotenv("backend/.env")

openai_key = os.getenv("OPENAI_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

print(f"OpenAI Key Length: {len(openai_key) if openai_key else None}")
print(f"Gemini Key Length: {len(gemini_key) if gemini_key else None}")

# Try a simple completion with Gemini (OpenAI compatibility endpoint)
try:
    resp = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={"Authorization": f"Bearer {gemini_key}"},
        json={
            "model": "gemini-2.0-flash",
            "messages": [{"role": "user", "content": "Hello, respond with 'Ok'"}]
        },
        timeout=10
    )
    print("Gemini OpenAI-compat response status:", resp.status_code)
    print("Gemini OpenAI-compat response:", resp.json() if resp.status_code == 200 else resp.text)
except Exception as e:
    print("Gemini OpenAI-compat failed:", e)

# Try native Gemini API endpoint
try:
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
        json={
            "contents": [{"parts": [{"text": "Hello, respond with 'Ok'"}]}]
        },
        timeout=10
    )
    print("Gemini Native response status:", resp.status_code)
    print("Gemini Native response:", resp.json() if resp.status_code == 200 else resp.text)
except Exception as e:
    print("Gemini Native failed:", e)

# Try a simple completion with OpenAI
try:
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {openai_key}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello, respond with 'Ok'"}]
        },
        timeout=10
    )
    print("OpenAI response status:", resp.status_code)
    print("OpenAI response:", resp.json() if resp.status_code == 200 else resp.text)
except Exception as e:
    print("OpenAI failed:", e)
