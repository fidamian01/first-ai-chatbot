import os
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

# Load environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("API key not found. Check your .env file.")

# Connect to Gemini
client = genai.Client(api_key=api_key)
connection = sqlite3.connect("chat_history.db")

connection.execute(
    """
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        message TEXT NOT NULL)"""
)
connection.commit()
connection.execute(
    """
      CREATE TABLE IF NOT EXISTS user_memory
      (
        memory_key TEXT PRIMARY KEY,
        memory_value TEXT NOT NULL
      )
      """
)
connection.commit()


def save_memory(key, value):
    connection.execute(
        """
        INSERT INTO user_memory (memory_key, memory_value)
        VALUES (?, ?)
        ON CONFLICT (memory_key)
        DO UPDATE SET memory_value = excluded.memory_value
        """,
        (key, value),
    )


def get_memories():
    saved_memories = connection.execute(
        "SELECT memory_key, memory_value From user_memory"
    ).fetchall()
    return saved_memories


# Temporary memory test
save_memory("name", "Ini")
save_memory("learning_goal", "Python and AI Engineering")

print("Saved user memories:")
print(get_memories())

# Conversation memory
conversation_history = []
saved_messages = connection.execute(
    "SELECT role, message FROM messages ORDER BY id"
).fetchall()
print("Saved messages:", saved_messages)

for role, message in saved_messages:
    conversation_history.append({"role": role, "parts": [{"text": message}]})
print(f"Loaded {len(conversation_history)} previous messages.")

# Chatbot personality
system_instruction = """
You are a friendly and patient Python and AI Engineering tutor.

Your job is to help beginners learn programming and AI engineering.

Follow these rules:

1. Explain technical concepts using simple language.
2. Break complicated topics into smaller steps.
3. Provide practical Python code examples where appropriate.
4. Explain code line by line when teaching new concepts.
5. When a student makes a coding mistake, explain why it happened
   and how to fix it.
6. Give students small exercises to test their understanding.
7. Do not assume the student already understands advanced concepts.
8. Encourage students to solve problems independently.
9. Be supportive, clear and educational.
"""


def ask_ai(question):

    user_message = {"role": "user", "parts": [{"text": question}]}

    conversation_history.append(user_message)

    try:
        config = types.GenerateContentConfig(system_instruction=system_instruction)

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite", contents=conversation_history, config=config
        )

        answer = response.text

        if not answer:
            raise ValueError("Gemini returned an empty response.")

        model_message = {"role": "model", "parts": [{"text": answer}]}

        conversation_history.append(model_message)

        connection.executemany(
            "INSERT INTO messages (role, message) VALUES (?, ?)",
            [("user", question), ("model", answer)],
        )

        connection.commit()

        return answer

    except errors.APIError as e:
        conversation_history.remove(user_message)
        return f"Gemini API error: {e}"

    except Exception as e:
        if conversation_history and conversation_history[-1]["role"] == "model":
            conversation_history.pop()

        if user_message in conversation_history:
            conversation_history.remove(user_message)

        return f"Unexpected error: {e}"


# Start chatbot
print("\nAI Chatbot Started!")
print("Conversation memory enabled.")
print("Permanent SQLite memory enabled.")
print("Python and AI Engineering Tutor mode enabled.")
print("Type 'exit' to stop.\n")

while True:
    question = input("You: ").strip()

    if question.lower() == "exit":
        print("Chatbot stopped.")
        break
    if not question:
        print("Please enter a message")
        continue

    answer = ask_ai(question)

    print("\nAI:", answer)
    print()

connection.close()
