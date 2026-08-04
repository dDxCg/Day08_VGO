"""
Task 9 — Retrieval Pipeline Hoàn Chỉnh.

Kết hợp semantic search + lexical search + reranking + PageIndex fallback
thành một pipeline thống nhất.

Logic:
    1. Chạy semantic_search + lexical_search song song
    2. Merge kết quả (RRF hoặc weighted fusion)
    3. Rerank
    4. Nếu top result score < threshold → fallback sang PageIndex
    5. Return top_k results

⚠️ BẪY THƯỜNG GẶP — đọc kỹ trước khi code:
    Nếu bạn dùng điểm RRF đã fuse (Task 7) để so với score_threshold, bạn sẽ gặp bug
    thật: RRF max score luôn ≈ 1/(k+1) ≈ 0.0164 (k=60) BẤT KỂ nội dung có liên quan
    hay không. Nếu đặt threshold thấp (như 0.005) để "hợp" với thang điểm RRF, thực
    chất KHÔNG câu hỏi nào đủ thấp để trigger fallback nữa — kể cả query hoàn toàn vô
    nghĩa vẫn trả về kết quả "hybrid" (rác) thay vì fallback đúng như thiết kế.

    Cách sửa đúng: giữ điểm cosine similarity GỐC của semantic_search (trước khi qua
    RRF) làm căn cứ quyết định fallback, tách biệt khỏi điểm RRF dùng để sắp xếp kết
    quả cuối cùng. Calibrate threshold bằng cách tự đo: chạy vài câu hỏi chắc chắn
    liên quan và vài câu chắc chắn lạc đề/rác qua semantic_search, xem khoảng cách
    điểm số giữa hai nhóm rồi chọn ngưỡng nằm giữa.
"""

import logging
import os

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# TODO: Calibrate threshold này bằng cách tự đo điểm cosine của semantic_search
# cho câu hỏi liên quan vs câu hỏi lạc đề (xem ghi chú ở trên) — ĐỪNG copy nguyên
# giá trị mẫu, mỗi corpus/embedding model sẽ cho khoảng điểm khác nhau.
SCORE_THRESHOLD = 0.3   # Nếu best score (cosine gốc) < threshold → fallback PageIndex
DEFAULT_TOP_K = 5
# Lưu ý: merge (bước 2) đã dùng RRF rồi — bước rerank ở đây KHÔNG thể lại là "rrf"
# (rerank_rrf cần nhiều ranked lists, còn đây chỉ có 1 list đã merge). Dùng cross_encoder.
RERANK_METHOD = "cross_encoder"  # "cross_encoder" | "mmr"

# Corpus trong chroma_db toàn tiếng Anh -> dịch query sang tiếng Anh trước khi
# retrieve để semantic/lexical search match đúng ngôn ngữ corpus. Câu trả lời cuối
# (Task 10) vẫn dùng query GỐC để LLM trả lời đúng ngôn ngữ user hỏi.
TRANSLATE_MODEL = os.getenv("CHAT_MODEL", "openai/gpt-4o-mini")


def translate_to_english(query: str) -> str:
    """Dịch query sang tiếng Anh để match corpus (chroma_db toàn tiếng Anh)."""
    from openai import OpenAI

    api_key = os.getenv("OPEN_ROUTER_API") or os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    response = client.chat.completions.create(
        model=TRANSLATE_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Translate the user's message to English. Output ONLY the translation, "
                            "no explanation. If it's already in English, return it unchanged.",
            },
            {"role": "user", "content": query},
        ],
        temperature=0,
    )
    translated = response.choices[0].message.content.strip()
    logger.info("translate_to_english: %r -> %r", query, translated)
    return translated


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
    retrieval_mode: str = "hybrid",  # "dense" | "hybrid" — for A/B testing (Task 10)
    rerank_method: str = RERANK_METHOD,  # "cross_encoder" | "mmr" — for A/B testing (Task 10)
) -> list[dict]:
    """
    Retrieval pipeline hoàn chỉnh với fallback logic.

    Pipeline:
        Query
          ├→ Semantic Search → dense_results (giữ điểm cosine gốc)
          ├→ Lexical Search  → sparse_results (bỏ qua nếu retrieval_mode="dense")
          │
          ├→ Merge (RRF, chỉ khi hybrid) → merged_results
          ├→ Rerank → reranked_results
          │
          └→ If dense_results[0]["score"] < threshold:
                └→ PageIndex Vectorless → fallback_results

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả cuối cùng
        score_threshold: Ngưỡng điểm cosine gốc tối thiểu (KHÔNG phải điểm RRF)
        use_reranking: Có áp dụng reranking hay không
        retrieval_mode: "dense" (chỉ semantic_search) hoặc "hybrid" (semantic + lexical + RRF)
        rerank_method: Method truyền cho rerank() khi use_reranking=True

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': str  # 'dense', 'hybrid' hoặc 'pageindex'
        }
    """
    if retrieval_mode not in ("dense", "hybrid"):
        raise ValueError(f"Unknown retrieval_mode: {retrieval_mode}")

    logger.info(
        "retrieve() start | query=%r top_k=%d retrieval_mode=%s use_reranking=%s rerank_method=%s",
        query, top_k, retrieval_mode, use_reranking, rerank_method,
    )

    # Step 0: Corpus toàn tiếng Anh -> dịch query trước khi search
    search_query = translate_to_english(query)

    # Step 1: Semantic search (luôn chạy — dùng cho fallback threshold + dense mode)
    dense_results = semantic_search(search_query, top_k=top_k * 2)
    logger.info("semantic_search -> %d results", len(dense_results))

    if retrieval_mode == "dense":
        merged = dense_results[:top_k * 2]
        for item in merged:
            item["source"] = "dense"
    else:
        # Step 2: Lexical search + merge bằng RRF
        sparse_results = lexical_search(search_query, top_k=top_k * 2)
        logger.info("lexical_search -> %d results", len(sparse_results))
        merged = rerank_rrf([dense_results, sparse_results], top_k=top_k * 2)
        for item in merged:
            item["source"] = "hybrid"
        logger.info("rerank_rrf merge -> %d results", len(merged))

    # Step 3: Rerank
    if use_reranking and merged:
        final_results = rerank(search_query, merged, top_k=top_k, method=rerank_method)
        for item in final_results:
            item.setdefault("source", merged[0]["source"])
        logger.info("rerank(%s) -> %d results", rerank_method, len(final_results))
    else:
        final_results = merged[:top_k]
        logger.info("reranking skipped, truncated to top_k=%d", len(final_results))

    # Step 4: Check threshold DÙNG ĐIỂM COSINE GỐC (dense_results), KHÔNG PHẢI RRF
    best_score = dense_results[0]["score"] if dense_results else 0.0
    logger.info("best dense (cosine) score=%.4f threshold=%.4f", best_score, score_threshold)
    if best_score < score_threshold:
        logger.warning(
            "Semantic best score (%.3f) < threshold (%.3f) -> falling back to PageIndex",
            best_score, score_threshold,
        )
        try:
            fallback = pageindex_search(search_query, top_k=top_k)
            logger.info("pageindex_search fallback -> %d results", len(fallback))
            if fallback:
                return fallback
        except Exception:
            # PageIndex chưa cấu hình (chưa upload_documents()/thiếu PAGEINDEX_API_KEY)
            # hoặc lỗi API — không để fallback lỗi làm sập cả pipeline, cứ trả về
            # kết quả hybrid hiện có (dù dưới threshold) còn hơn không có gì.
            logger.exception("pageindex_search fallback failed, returning hybrid results instead")

    logger.info("retrieve() done -> %d results", len(final_results[:top_k]))
    return final_results[:top_k]


if __name__ == "__main__":
    test_queries = [
        "What is the tuition fee at RMIT Vietnam?",
        "How do I book a library study room?",
        "What scholarships are available for international students?",
        "xyzabc123nonsense",  # Query không có kết quả → test fallback
    ]

    for q in test_queries:
        print(f"\nQuery: {q}")
        print("-" * 60)
        results = retrieve(q, top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. [{r['score']:.3f}] [{r['source']}] {r['content'][:80]}...")
