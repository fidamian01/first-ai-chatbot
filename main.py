import os
import sqlite3
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

ALLOWED_MEMORY_KEYS = {
    "name",
    "learning_goal",
    "learning_style",
    "occupation",
    "interests",
}

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


def delete_memory(key):
    connection.execute(
        """
        DELETE FROM user_memory   
        WHERE memory_key = ?
        
        """,
        (key,),
    )
    connection.commit()


def update_memory(key, value):
    connection.execute(
        """
        UPDATE user_memory      
        SET memory_value = ?
        WHERE memory_key = ?
        
        """,
        (value, key),
    )
    connection.commit()


def get_memories():
    saved_memories = connection.execute(
        "SELECT memory_key, memory_value From user_memory"
    ).fetchall()
    return saved_memories


def display_memories():
    memories = get_memories()

    if not memories:
        print("No saved memories found.")
        return

    print("\n Here is what i remember about you:\n")
    for key, value in memories:
        print(f"-{key.replace('_', ' ').title()}: {value}")


def get_memory_context():
    memories = get_memories()

    if not memories:
        return "No saved information yet"
    memory_context = "Here is what you know about the user:\n"
    for key, value in memories:
        memory_context += f"-{key}: {value}\n"
    return memory_context


import json


def extract_memories(user_message):

    extraction_prompt = f"""
    You are a personal memory extraction system.

    Analyse the user's message and identify explicit,
    useful personal information that is likely to remain
    relevant in future conversations.

    Only extract facts the user clearly states about themselves.

    Allowed memory categories:
    - name
    - learning_goal
    - learning_style
    - occupation
    - interests

    IMPORTANT RULES:

    1. Do not extract information from questions.
    2. Do not extract hypothetical statements.
    3. Do not extract guesses or assumptions.
    4. Do not extract temporary activities or short-term plans.
    5. Do not treat examples as personal information.
    6. Do not change the meaning of the user's statements.
    7. Only extract information that belongs to the user.
    8. If the user corrects previously stated information,
       extract the corrected information.

    Return only a valid JSON object.

    Example 1:
    User: My name is Ini.
    Output: {{"name": "Ini"}}

    Example 2:
    User: I prefer learning through practical exercises.
    Output: {{"learning_style": "practical coding exercises"}}

    Example 3:
    User: What if I wanted to become a data scientist?
    Output: {{}}

    Example 4:
    User: I might start learning Java next year.
    Output: {{}}

    Example 5:
    User: I am interested in machine learning.
    Output: {{"interests": "machine learning"}}

    If no useful information is found, return {{}}.

    User message:
    {user_message}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=extraction_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0
            ),
        )

        if not response.text:
            print("Gemini returned an empty response.")
            return {}

        extracted_data = json.loads(response.text)

        if not isinstance(extracted_data, dict):
            print("Unexpected response format.")
            return {}

        return extracted_data

    except json.JSONDecodeError:
        print("Gemini returned invalid JSON.")
        return {}

    except Exception as e:
        print("Memory extraction error:", e)
        return {}


def validate_memories(extracted_data):

    validated_memories = {}

    invalid_values = {"unknown", "none", "not specified", "not sure", "i don't know"}

    for key, value in extracted_data.items():
        if key not in ALLOWED_MEMORY_KEYS:
            continue

        if not isinstance(value, str):
            continue

        value = value.strip()

        if not value or len(value) > 200:
            continue

        if value.casefold() in invalid_values:
            continue

        validated_memories[key] = value

    return validated_memories


def update_user_memories(user_message):

    extracted_data = extract_memories(user_message)

    validated_data = validate_memories(extracted_data)

    for key, value in validated_data.items():
        save_memory(key, value)

    return validated_data


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
        memory_context = get_memory_context()
        config = types.GenerateContentConfig(
            system_instruction=f"""
                {system_instruction}

                IMPORTANT USER INFORMATION:
                {memory_context}

                Use this information to personalise your responses.
                Treat these saved memories as information provided by the user.
                Do not invent personal information that is not stored.
                """
        )

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
    try:
        saved_memories = update_user_memories(question)

        if saved_memories:
            print("Memory updated successfully.")
    except Exception as e:
        print("Memory update error", e)


# Test memory extraction

test_messages = [
    "My name is Ini",
    "I prefer learning through practical coding exercises",
    "What if I wanted to become a data scientist?",
    "I might start learning Java next year",
    "I am interested in machine learning",
]

for message in test_messages:
    print("\nUser message:", message)

    result = extract_memories(message)

    print("Extracted memory:", result)


# Test memory validation

print("\nTesting memory validation...")

test_data = {
    "name": "Ini",
    "learning_goal": "Python and AI Engineering",
    "learning_style": "   practical coding exercises   ",
    "occupation": "",
    "interests": "unknown",
    "password": "123456",
    "extra_information": "some random information",
}

result = validate_memories(test_data)

print("Validated memories:", result)

print("\nMemories before deletion:")
print(get_memories())

delete_memory("learning_style")

print("\nMemories after deletion:")
print(get_memories())


print("\nTesting memory update...")

update_memory("learning_goal", "AI Engineering and Machine Learning")

print("\nMemories after update:")
print(get_memories())

print("\nTesting memory display...")

display_memories()

connection.close()
