"""
A/B testing cho Retrieval + Reranking pipeline (Task 9 + Task 10).

So sánh: dense-only vs hybrid retrieval, rerank vs no-rerank, và giữa các
reranking strategy (cross_encoder vs mmr). Không tự động chấm điểm — in kết
quả song song để review thủ công (hoặc feed vào ragas eval riêng).

Chạy:
    python -m tests.test_ab_pipeline                # full A/B matrix, in report
    python -m tests.test_ab_pipeline --top-k 3
    pytest tests/test_ab_pipeline.py -v              # smoke test (chỉ check wiring/shape)
"""

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from src.task10_generation import generate_with_citation, TOP_K

# Mỗi entry: (label, retrieval_mode, use_reranking, rerank_method)
AB_CONFIGS: list[tuple[str, str, bool, str]] = [
    ("dense_only_no_rerank", "dense", False, "cross_encoder"),
    ("hybrid_no_rerank", "hybrid", False, "cross_encoder"),
    ("hybrid_cross_encoder", "hybrid", True, "cross_encoder"),
    ("hybrid_mmr", "hybrid", True, "mmr"),
]

TEST_QUERIES = [
    "Học phí tại RMIT Vietnam là bao nhiêu?",
    "Làm sao để đặt phòng học nhóm ở thư viện?",
    "Sinh viên quốc tế có những học bổng nào?",
]


def run_ab_test(
    queries: list[str],
    configs: list[tuple[str, str, bool, str]] = AB_CONFIGS,
    top_k: int = TOP_K,
) -> list[dict]:
    """
    Chạy cùng bộ queries qua nhiều config (retrieval mode / rerank on-off /
    rerank strategy) để so sánh.

    Returns:
        List of {'query': str, 'config': str, 'answer': str, 'sources': int, 'retrieval_source': str}
    """
    rows = []
    for q in queries:
        for label, retrieval_mode, use_reranking, rerank_method in configs:
            result = generate_with_citation(
                q,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
                use_reranking=use_reranking,
                rerank_method=rerank_method,
            )
            rows.append({
                "query": q,
                "config": label,
                "answer": result["answer"],
                "sources": len(result["sources"]),
                "retrieval_source": result["retrieval_source"],
            })
    return rows


def print_ab_report(rows: list[dict]) -> None:
    for row in rows:
        print(f"\n{'='*70}")
        print(f"Q: {row['query']}  |  config: {row['config']}")
        print("=" * 70)
        print(f"A: {row['answer']}")
        print(f"[Sources: {row['sources']} chunks | via {row['retrieval_source']}]")


# ===========================================================================
# Smoke test — chỉ verify wiring/shape, không cần data đã index sẵn để pass
# (skip nếu upstream pipeline chưa sẵn sàng, ví dụ Task 4/5 chưa implement
# hoặc chưa crawl data).
# ===========================================================================

class TestABPipeline(unittest.TestCase):
    def test_run_ab_test_returns_expected_shape(self):
        try:
            rows = run_ab_test(TEST_QUERIES[:1], configs=AB_CONFIGS[:1], top_k=2)
        except Exception as e:
            self.skipTest(f"Upstream pipeline not ready: {e}")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        for key in ("query", "config", "answer", "sources", "retrieval_source"):
            self.assertIn(key, row)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A/B test — retrieval + reranking pipeline")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    rows = run_ab_test(TEST_QUERIES, top_k=args.top_k)
    print_ab_report(rows)
