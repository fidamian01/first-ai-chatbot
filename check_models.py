from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("\nAvailable models that support text generation:\n")

for model in client.models.list():
    supported_actions = model.supported_actions or []

    if "generateContent" in supported_actions:
        print(model.name)
