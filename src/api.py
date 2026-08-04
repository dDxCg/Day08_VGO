"""
FastAPI Backend — RAG pipeline qua HTTP, streaming answer (SSE).

Chạy:
    uv run uvicorn src.api:app --reload --port 8000

Endpoints:
    POST /chat/stream  — SSE stream: mỗi event là 1 chunk answer, event cuối "done"
    POST /chat          — non-streaming, trả full answer 1 lần
    GET  /health
"""

import json
import logging

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .task10_generation import generate_with_citation, generate_with_citation_stream, TOP_K

logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Chatbot API")


class ChatRequest(BaseModel):
    query: str
    top_k: int = TOP_K
    retrieval_mode: str = "hybrid"     # "dense" | "hybrid"
    use_reranking: bool = True
    rerank_method: str = "cross_encoder"  # "cross_encoder" | "mmr"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    logger.info("POST /chat | query=%r", req.query)
    result = generate_with_citation(
        req.query,
        top_k=req.top_k,
        retrieval_mode=req.retrieval_mode,
        use_reranking=req.use_reranking,
        rerank_method=req.rerank_method,
    )
    return result


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    logger.info("POST /chat/stream | query=%r", req.query)

    def event_stream():
        for event in generate_with_citation_stream(
            req.query,
            top_k=req.top_k,
            retrieval_mode=req.retrieval_mode,
            use_reranking=req.use_reranking,
            rerank_method=req.rerank_method,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)