import os
from dotenv import load_dotenv
from google import genai
from google.genai import errors


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("API key not found")

client = genai.Client(api_key=api_key)


def ask_ai(question):
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=question,
            )
            return response.text
        except errors.ServerError as e:
            return f"Gemini server error {e}"
        except errors.APIError as e:
            return f"Gemini API error {e}"
        except Exception as e:
            return f"An unnepected error:{e}"


while True:
    question = input("\nYou:")
    if question.lower().strip() == "exit":
        print("Chatbot stopped.")
        break
    answer = ask_ai(question)
    print(f"AI: {answer}")
    print()
