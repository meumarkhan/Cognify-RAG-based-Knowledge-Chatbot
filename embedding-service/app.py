from fastapi import FastAPI, Request
from sentence_transformers import SentenceTransformer
from typing import List, Union

app = FastAPI(title="Embedding API", version="1.0")

# Load model once at startup
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


@app.post("/embed")
async def get_embedding(request: Request):
    body = await request.json()
    inputs: Union[str, List[str]] = body.get("input")

    if inputs is None:
        return {"error": "No input provided"}

    # Normalize to list
    if isinstance(inputs, str):
        inputs = [inputs]

    # Encode batch
    embeddings = model.encode(inputs, batch_size=32).tolist()

    return {
        "data": [
            {"embedding": emb, "dimension": len(emb)}
            for emb in embeddings
        ],
        "count": len(embeddings)
    }
