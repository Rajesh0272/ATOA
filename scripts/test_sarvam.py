from sarvamai import SarvamAI
import os

api_key = os.getenv("SARVAM_API_KEY")

print("=" * 70)
print("SARVAM API TEST")
print("=" * 70)

print("[INPUT] API key loaded:", bool(api_key))
print("[INPUT] Model: sarvam-105b")

client = SarvamAI(
    api_subscription_key=api_key
)

response = client.chat.completions(
    model="sarvam-105b",
    messages=[
        {
            "role": "user",
            "content": "Explain what a software test case is in 3 sentences."
        }
    ],
)

print()
print("[OUTPUT]")
print(response.choices[0].message.content)

print("=" * 70)