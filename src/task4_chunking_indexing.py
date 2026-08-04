"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (ChromaDB khuyến cáo — đơn giản, local, không cần Docker)

Chunking options (langchain-text-splitters):
    - RecursiveCharacterTextSplitter: an toàn, phổ biến
    - MarkdownHeaderTextSplitter: tốt cho file có heading
    - SemanticChunker: dùng embedding để tách (nâng cao)

Embedding model options:
    - sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ)
    - BAAI/bge-m3 (1024 dim, multilingual, tốt cho cả tiếng Việt lẫn tiếng Anh)
    - OpenAI text-embedding-3-small (1536 dim, API)

Vector store options:
    - ChromaDB (khuyến cáo: đơn giản, local persistent, không cần Docker)
    - Weaviate (hỗ trợ hybrid search built-in, cần Docker/Cloud)
    - FAISS (chỉ dense search)

Embedding: gọi qua OpenRouter /embeddings API (OpenAI-compatible), model id đọc từ
.env EMBEDDING_MODEL, key từ .env OPEN_ROUTER_API — không cần tải model local.

Cài đặt:
    pip install langchain-text-splitters openai chromadb

Lưu ý quan trọng: nếu sau này đổi corpus (đổi chủ đề, thêm/bớt tài liệu), phải XÓA
chroma_db/ cũ trước khi reindex — nếu không, chunk cũ và mới sẽ tồn tại lẫn lộn
trong cùng collection, retrieval sẽ trả về kết quả rác từ dữ liệu cũ.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# Chọn RecursiveCharacterTextSplitter: an toàn, không phụ thuộc cấu trúc heading
# đồng đều giữa 2 loại nguồn (PDF chính sách vs JSON tin tức đã convert).
# CHUNK_SIZE=800: đủ giữ trọn 1 đoạn chính sách/tin hoàn chỉnh mà không vượt quá
# context window khi nhồi nhiều chunk vào prompt Task 10.
# CHUNK_OVERLAP=100 (~12.5%): tránh cắt đôi câu quan trọng ở ranh giới 2 chunk.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
CHUNKING_METHOD = "recursive"  # "recursive" | "markdown_header" | "semantic"

# Embed qua OpenRouter /embeddings (OpenAI-compatible) thay vì tải model local —
# tránh phải tải sentence-transformers model (vài GB) về máy. Đọc model id từ .env
# (EMBEDDING_MODEL) để dễ đổi mà không sửa code.
# Lưu ý: họ E5 (multilingual-e5-*) yêu cầu prefix "query: "/"passage: " trước text khi
# encode để đạt chất lượng tốt nhất — xem embed_chunks() và task5_semantic_search.py.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = 1024
_IS_E5_MODEL = "e5-" in EMBEDDING_MODEL.lower()

OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_API")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ChromaDB: local persistent, không cần Docker, đủ nhanh cho quy mô corpus của bài lab.
VECTOR_STORE = "chromadb"  # "chromadb" | "weaviate" | "faiss"
COLLECTION_NAME = "university_services_docs"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        doc_type = "legal" if "legal" in str(md_file) else "news"
        documents.append({
            "content": content,
            "metadata": {"source": md_file.name, "type": doc_type}
        })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for i, chunk_text in enumerate(splits):
            chunks.append({
                "content": chunk_text,
                "metadata": {**doc["metadata"], "chunk_index": i}
            })
    return chunks


_embedding_client = None  # cache: tránh tạo lại OpenAI client mỗi lần gọi
_chroma_client = None


def get_embedding_client():
    """Trả về OpenAI-compatible client (OpenRouter) dùng chung cho Task 4 (index) và Task 5 (query)."""
    global _embedding_client
    if _embedding_client is None:
        from openai import OpenAI
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPEN_ROUTER_API not set in .env")
        _embedding_client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    return _embedding_client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed 1 batch text qua OpenRouter /embeddings. Dùng chung cho index (Task 4) và query (Task 5)."""
    client = get_embedding_client()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


def get_collection():
    """Trả về ChromaDB collection dùng chung cho Task 4 (index) và Task 5 (query)."""
    global _chroma_client
    import chromadb

    if _chroma_client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    texts = [c["content"] for c in chunks]
    if _IS_E5_MODEL:
        texts = [f"passage: {t}" for t in texts]
    embeddings = embed_texts(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
    collection = get_collection()

    ids = [f"{c['metadata']['source']}_chunk_{c['metadata']['chunk_index']}" for c in chunks]
    collection.upsert(
        ids=ids,
        documents=[c["content"] for c in chunks],
        embeddings=[c["embedding"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
