
import os
import requests
import base64
from pathlib import Path
from dotenv import load_dotenv

# Calculate path to .env relative to this script
# If script is in root, .env is in backend/.env
env_path = Path(__file__).parent / "backend" / ".env"
result = load_dotenv(env_path)

print(f"Loaded .env from {env_path}: {result}")

API_KEY = os.getenv("SARVAM_API_KEY")
print(f"API Key present: {bool(API_KEY)}")
if API_KEY:
    print(f"API Key starts with: {API_KEY[:4]}...")

url = "https://api.sarvam.ai/text-to-speech"
payload = {
    "text": "Hello, this is a test of the Sarvam API.",
    "target_language_code": "hi-IN",
    "model": "bulbul:v3-beta",
    "speaker": "Shubh", # Test capitalized speaker name
    "output_audio_codec": "wav"
}
headers = {
    "api-subscription-key": API_KEY,
    "Content-Type": "application/json"
}

print(f"Sending request to {url}...")
try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error Response: {response.text}")
    else:
        data = response.json()
        audios = data.get("audios", [])
        if audios:
            print("Audio data received successfully.")
            import base64
            with open("test_audio.wav", "wb") as f:
                f.write(base64.b64decode(audios[0]))
            print("Saved test_audio.wav")
        else:
            print("No audio data in response!")
except Exception as e:
    print(f"Exception: {e}")
