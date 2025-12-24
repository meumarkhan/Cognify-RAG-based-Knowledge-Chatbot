import pdfplumber
from langchain.text_splitter import RecursiveCharacterTextSplitter
from fastapi import UploadFile
import requests
from dotenv import load_dotenv
import os
import redis

load_dotenv()

EMBEDDING_SERVER_URL = os.getenv("EMBEDDING_SERVER_URL", "http://localhost:8000/embed")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True
)

chatId=0

def extract_text_from_file(file: UploadFile) -> str:
    text = ""
    file.file.seek(0)

    if file.content_type == "application/pdf" or file.filename.lower().endswith(".pdf"):
        with pdfplumber.open(file.file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or " "
    else:
        text = file.file.read().decode("utf-8", errors="ignore")
    return text


def chunk_text(text: str, chunk_size: int =1000, overlap: int = 200) -> list:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=len,
    )
    chunks = splitter.split_text(text)
    return chunks

def get_embeddings(chunks: list[str], batch_size: int = 32) -> list[list[float]]:
    """
    Get embeddings for text chunks.
    Uses batching for efficiency.
    """
    embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        data = {"input": batch}
        r = requests.post(EMBEDDING_SERVER_URL, json=data)

        if r.status_code != 200:
            raise Exception(f"Embedding API error: {r.text}")

        batch_embeddings = [item["embedding"] for item in r.json()["data"]]
        embeddings.extend(batch_embeddings)

    return embeddings

def clear_redis():
    redis_client.flushdb()
    global chatId
    chatId=0
    print("Redis database cleared.")

def save_to_redis(message: str, role: str):
    # Get a persistent, incrementing chat ID
    chat_id = redis_client.incr("chat_counter")

    # Save the message with role in a hash (so you can fetch by ID)
    redis_client.hset(f"chat:{chat_id}", mapping={"role": role, "message": message})

    # Also push to a list to maintain order
    redis_client.rpush("chat_history", chat_id)

    return chat_id


def get_chat_history():
    history = []
    # Get IDs in order
    chat_ids = redis_client.lrange("chat_history", 0, -1)
    for chat_id in chat_ids:
        entry = redis_client.hgetall(f"chat:{chat_id}")
        if entry:
            history.append({"role": entry["role"], "message": entry["message"], "id": int(chat_id)})
    return history


def get_response_by_id(request_id: int):
    key = f"chat:{request_id}"
    if redis_client.exists(key):
        entry = redis_client.hgetall(key)
        return entry.get("message", None)
    return None
