import os
import re
from dotenv import load_dotenv
from google import genai
from google.genai import errors


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("API key not found")

client = genai.Client(api_key=api_key)

conversation_history = []


def ask_ai(question):

    conversation_history.append({"role": "user", "parts": [{"text": question}]})
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=conversation_history,
        )
        answer = response.text

        conversation_history.append({"role": "model", "parts": [{"text": answer}]})
        return answer

    except errors.ServerError as e:
        conversation_history.pop()  # Remove the last user message if there's an error
        return f"Gemini server error {e}"
    except errors.APIError as e:
        conversation_history.pop()  # Remove the last user message if there's an error
        return f"Gemini API error {e}"
    except Exception as e:
        conversation_history.pop()  # Remove the last user message if there's an error
        return f"An unexpected error occurred: {e}"


print("AI Chatbot Started")
print("conversation memory enabled")
print("Type 'exit' to stop.\n")

while True:
    question = input("You: ")

    if question.lower().strip() == "exit":
        print("Chatbot stopped.")
        break
    answer = ask_ai(question)
    print(f"AI: {answer}\n")
    print()
