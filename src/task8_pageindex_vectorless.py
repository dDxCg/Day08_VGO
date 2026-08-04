"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.

Cài đặt:
    pip install pageindex

Hướng dẫn:
    1. Đăng ký account tại pageindex.ai
    2. Lấy API key
    3. Upload documents
    4. Query sử dụng PageIndex API

Lưu ý: API `/retrieval` của PageIndex hiện đã deprecated (vẫn hoạt động, nhưng response
có field "deprecation" cảnh báo) và trả kết quả trong "retrieved_nodes" — mỗi node có
"relevant_contents": list[list[{section_title, relevant_content}]]. In response thật ra
(json.dumps(...)) trước khi viết logic parse, đừng đoán schema từ ví dụ code cũ.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fpdf import FPDF
from pageindex.client import PageIndexClient

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
PDF_CACHE_DIR = Path(__file__).parent.parent / "data" / "pageindex_pdf"
DOC_MAP_PATH = Path(__file__).parent.parent / "data" / "pageindex_docs.json"

POLL_INTERVAL_SEC = 3
POLL_TIMEOUT_SEC = 300


def _md_to_pdf(md_file: Path) -> Path:
    """Convert 1 markdown file sang PDF đơn giản (fpdf2) để PageIndex nhận được."""
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = PDF_CACHE_DIR / (md_file.stem + ".pdf")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    text = md_file.read_text(encoding="utf-8")
    for line in text.splitlines():
        pdf.multi_cell(0, 6, line.encode("latin-1", "replace").decode("latin-1"))
    pdf.output(str(pdf_path))
    return pdf_path


def _poll_until_ready(client: PageIndexClient, doc_id: str) -> None:
    start = time.time()
    while time.time() - start < POLL_TIMEOUT_SEC:
        if client.is_retrieval_ready(doc_id):
            return
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"PageIndex doc {doc_id} not ready after {POLL_TIMEOUT_SEC}s")


def upload_documents() -> dict[str, str]:
    """
    Upload toàn bộ markdown documents lên PageIndex.

    Returns:
        dict: {filename: doc_id} — cũng được lưu vào DOC_MAP_PATH để tái sử dụng.
    """
    client = PageIndexClient(api_key=PAGEINDEX_API_KEY)

    doc_map: dict[str, str] = {}
    md_files = list(STANDARDIZED_DIR.rglob("*.md"))
    if not md_files:
        raise RuntimeError(
            f"No documents found in {STANDARDIZED_DIR}. "
            "Run task2 (crawl) + task3 (convert) first."
        )

    for md_file in md_files:
        pdf_path = _md_to_pdf(md_file)
        resp = client.submit_document(str(pdf_path))
        doc_id = resp.get("doc_id") or resp.get("id")
        doc_map[md_file.name] = doc_id
        print(f"  ✓ Uploaded: {md_file.name} -> {doc_id}")

    DOC_MAP_PATH.write_text(json.dumps(doc_map, indent=2), encoding="utf-8")

    print("  Waiting for PageIndex tree/OCR processing...")
    for name, doc_id in doc_map.items():
        _poll_until_ready(client, doc_id)
        print(f"  ✓ Ready: {name}")

    return doc_map


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    if not DOC_MAP_PATH.exists():
        raise RuntimeError("No PageIndex docs uploaded yet. Run upload_documents() first.")

    doc_map = json.loads(DOC_MAP_PATH.read_text(encoding="utf-8"))
    client = PageIndexClient(api_key=PAGEINDEX_API_KEY)

    results = []
    for doc_name, doc_id in doc_map.items():
        resp = client.submit_query(doc_id=doc_id, query=query)
        retrieval_id = resp.get("retrieval_id") or resp.get("id")

        retrieval = client.get_retrieval(retrieval_id)
        start = time.time()
        while retrieval.get("status") not in ("completed", "failed"):
            if time.time() - start > POLL_TIMEOUT_SEC:
                raise TimeoutError(f"PageIndex retrieval {retrieval_id} timed out")
            time.sleep(POLL_INTERVAL_SEC)
            retrieval = client.get_retrieval(retrieval_id)

        # In raw response để verify schema thật trước khi tin cậy parse logic bên dưới
        print(json.dumps(retrieval, indent=2, ensure_ascii=False)[:2000])

        rank = 0
        for node in retrieval.get("retrieved_nodes", []):
            for group in node.get("relevant_contents", []):
                for item in group:
                    rank += 1
                    results.append({
                        "content": item.get("relevant_content", ""),
                        "score": 1.0 / rank,
                        "metadata": {"section": item.get("section_title"), "doc": doc_name},
                        "source": "pageindex",
                    })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("tuition fee payment methods", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
