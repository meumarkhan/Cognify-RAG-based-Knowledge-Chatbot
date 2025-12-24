from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
import llm
import services
import uuid
from chromaDB import collection, reset_collection

app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

@app.get("/")
async def health():
    return {"message": "Server is running"}

@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    # Extract text
    text = services.extract_text_from_file(file)
    # Chunk text
    chunks = services.chunk_text(text)
    # Get embeddings
    embeddings = services.get_embeddings(chunks)

    # Generate a unique file_id for this file upload
    file_id = str(uuid.uuid4())

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "file_id": file_id,          # unique file_id
            "file_name": file.filename,  # original filename (optional, for display)
            "chunk_index": i
        })

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return {
        "message": "File uploaded successfully",
        "file_name": file.filename,
        "file_id": file_id,
        "total_chunks": len(chunks)
    }



@app.post("/api/v1/query")
async def make_query(request: QueryRequest, background_tasks: BackgroundTasks):

    request_id= services.save_to_redis(request.query, "user")

    def process_query():
        try:
            # Step 1: Generate embeddings
            query_embedding = services.get_embeddings([request.query])[0]

            # Step 2: Perform similarity search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=request.top_k,
            )

            # Step 3: Call the LLM with retrieved context
            try:
                response = llm.call_llm(request.query, results["documents"][0])
            except Exception as e:
                # Save error message in Redis to keep chat consistent
                error_msg = "⚠️ LLM service is currently unavailable. Please try again later."
                services.save_to_redis(error_msg, "assistant")

                raise HTTPException(
                    status_code=503,
                    detail=f"LLM error: {str(e)}"
                )

            # Step 4: Save successful response
            services.save_to_redis(response, "assistant")
            return {"answer": response}

        except Exception as e:
            # Save generic error state in Redis too
            error_msg = "❌ An error occurred while processing your query."
            services.save_to_redis(error_msg, "assistant")

            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error: {str(e)}"
            )

    background_tasks.add_task(process_query)

    return {"status": "processing", "request_id": request_id}


@app.get("/api/v1/query-result/{request_id}")
async def get_query_result(request_id: int):
    response= services.get_response_by_id(request_id+1)
    if response is None:
        return {"status": "processing", "answer": None}
    return {"status": "done", "answer": response}

@app.get("/api/v1/files")
async def list_files():
    files = collection.get(include=["metadatas"])
    all_metadatas = files["metadatas"] if files["metadatas"] else []
    unique_files = {}
    for metadata in all_metadatas:
        if metadata and "file_id" in metadata:
            unique_files[metadata["file_id"]] = metadata.get("file_name", "unknown")

    return {"files": [{"file_id": fid, "file_name": fname} for fid, fname in unique_files.items()]}


@app.delete("/api/v1/files/{file_id}")
async def delete_file(file_id: str):
    files = collection.get(include=["metadatas"])
    all_ids = files["ids"] if files["ids"] else []
    all_metadatas = files["metadatas"] if files["metadatas"] else []
    
    ids_to_delete = [
        idx for idx, metadata in zip(all_ids, all_metadatas)
        if metadata and metadata.get("file_id") == file_id
    ]

    if not ids_to_delete:
        return {"message": f"No chunks found for file_id {file_id}"}

    collection.delete(ids=ids_to_delete)

    return {"message": f"File with file_id {file_id} deleted successfully"}


@app.get("/api/v1/new-session")
async def new_session():
    services.clear_redis()
    global collection
    collection = reset_collection()
    return {"message": "New session started, all data cleared"}

@app.get("/api/v1/all-chats")
async def get_all_chats():
    history = services.get_chat_history()
    return {"chats": history}