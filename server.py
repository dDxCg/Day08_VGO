"""
Backend server cho ui-design/prototype.html — nối UI prototype với RAG pipeline thật
(Task 9 retrieval + Task 10 generation streaming), thay vì dữ liệu demo hardcode.

Chạy:
    python server.py
    # hoặc: uvicorn server:app --reload
Mở: http://127.0.0.1:8000/
"""

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.task10_generation import generate_with_citation_stream

logging.basicConfig(level=logging.INFO)

UI_DIR = Path(__file__).parent / "ui-design"

app = FastAPI(title="RMIT Student Services Assistant API")
app.mount("/image", StaticFiles(directory=str(UI_DIR / "image")), name="image")


@app.get("/")
def index():
    return FileResponse(str(UI_DIR / "prototype.html"))


class AskRequest(BaseModel):
    query: str
    top_k: int = 5
    retrieval_mode: str = "hybrid"  # "dense" | "hybrid"
    use_reranking: bool = True
    rerank_method: str = "cross_encoder"  # "cross_encoder" | "mmr"


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/ask")
def ask(req: AskRequest):
    """
    Server-Sent Events stream: mỗi dòng "data: {...}\\n\\n" là 1 event JSON.
    Event types: 'delta' (token mới từ LLM), 'done' (kết thúc, có sources đầy đủ),
    'error' (retrieval/generation lỗi — UI hiển thị banner lỗi + nút thử lại).
    """
    def event_stream():
        try:
            for event in generate_with_citation_stream(
                req.query,
                top_k=req.top_k,
                retrieval_mode=req.retrieval_mode,
                use_reranking=req.use_reranking,
                rerank_method=req.rerank_method,
            ):
                yield _sse(event)
        except Exception as e:
            logging.exception("generate_with_citation_stream failed")
            yield _sse({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
