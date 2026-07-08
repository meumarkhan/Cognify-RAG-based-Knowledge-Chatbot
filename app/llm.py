import os
import json
import requests
from typing import List
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL = os.getenv("MODEL")

def call_llm(user_query: str, context_chunks: List[str]) -> str:
    """
    Calls the LLM with user query and context (from vectorDB).

    Args:
        user_query (str): The question asked by the user.
        context_chunks (List[str]): List of relevant context strings from vectorDB.

    Returns:
        str: The generated answer from the LLM.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in environment variables.")

    # Combine retrieved chunks into a context prompt
    context_text = "\n\n".join(context_chunks) if context_chunks else "No additional context provided."

    # Build system + user messages
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Use the provided context to answer the question. "
                       "If the answer is not in the context, try to answer from your knowledge."
        },
        {
            "role": "user",
            "content": f"Context:\n{context_text}\n\nQuestion: {user_query}"
        }
    ]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
    }

    response = requests.post(GROQ_API_URL, headers=headers, data=json.dumps(payload))

    if response.status_code != 200:
        raise RuntimeError(f"Groq API error {response.status_code}: {response.text}")

    data = response.json()
    return data["choices"][0]["message"]["content"]
