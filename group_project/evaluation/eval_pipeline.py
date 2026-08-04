"""
RAG Evaluation Pipeline — RAGAS.

Yêu cầu:
    1. Load golden_dataset.json (15 Q&A, cover injection / ambiguous / complex,
       độ khó easy-medium-hard)
    2. Chạy RAG pipeline (Task 9 + 10) trên từng question
    3. Evaluate với 4 metrics: faithfulness, answer_relevancy, context_recall, context_precision
    4. So sánh A/B ít nhất 2 configs (dense-only vs hybrid, rerank vs no-rerank)
    5. Export results ra results.md

Lưu ý rate limit nếu dùng model OpenRouter ":free": RAGAS gọi LLM RẤT NHIỀU LẦN (không
phải 1 lần/câu hỏi mà nhiều lần/metric/câu hỏi). Model free của OpenRouter giới hạn
50 request/ngày CHO CẢ TÀI KHOẢN. Nếu bị rate limit giữa chừng, giảm subset câu hỏi hoặc
nạp credit.

Chạy:
    uv run python -m group_project.evaluation.eval_pipeline
"""

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"


def load_golden_dataset() -> list[dict]:
    """Load golden dataset từ JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# RAGAS setup — LLM + Embeddings qua OpenRouter (LangChain wrapper)
# =============================================================================

def _get_ragas_llm_embeddings():
    """
    RAGAS cần 1 LLM (judge) + 1 embedding model để tính các metrics.
    Dùng lại CHAT_MODEL / EMBEDDING_MODEL trong .env qua OpenRouter, wrap bằng
    LangChain (RAGAS hiện expose adapter cho LangChain LLM/Embeddings).
    """
    import os

    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    api_key = os.getenv("OPEN_ROUTER_API")
    base_url = "https://openrouter.ai/api/v1"
    chat_model = os.getenv("CHAT_MODEL", "openai/gpt-4o-mini")
    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")

    llm = LangchainLLMWrapper(
        ChatOpenAI(model=chat_model, api_key=api_key, base_url=base_url, temperature=0)
    )
    embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(model=embedding_model, api_key=api_key, base_url=base_url)
    )
    return llm, embeddings


# =============================================================================
# Run RAG pipeline over golden dataset -> RAGAS-shaped dataset
# =============================================================================

def run_pipeline_on_dataset(golden_dataset: list[dict], **pipeline_kwargs) -> "Dataset":
    """
    Chạy generate_with_citation() trên từng câu hỏi trong golden dataset với
    1 config cụ thể (pipeline_kwargs truyền thẳng xuống retrieve()/generate).

    Returns:
        HuggingFace Dataset shape RAGAS cần: question, answer, contexts, ground_truth
    """
    from datasets import Dataset

    from src.task10_generation import generate_with_citation

    eval_data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    for item in golden_dataset:
        logger.info("Running pipeline for [%s] %r", item.get("id", "?"), item["question"])
        try:
            result = generate_with_citation(item["question"], **pipeline_kwargs)
        except Exception as e:
            logger.error("Pipeline failed for %s: %s", item.get("id", "?"), e)
            result = {"answer": "", "sources": []}

        eval_data["question"].append(item["question"])
        eval_data["answer"].append(result["answer"])
        eval_data["contexts"].append([c["content"] for c in result["sources"]] or [""])
        eval_data["ground_truth"].append(item["expected_answer"])

    return Dataset.from_dict(eval_data)


def evaluate_with_ragas(dataset: "Dataset") -> "pd.DataFrame":
    """Chạy RAGAS evaluate() với 4 metrics chính, trả về pandas DataFrame per-row."""
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    from ragas.run_config import RunConfig

    llm, embeddings = _get_ragas_llm_embeddings()

    # max_workers thấp: tránh dồn request đồng thời gây rate-limit/timeout trên OpenRouter
    # (raise_exceptions=False -> job lỗi thành NaN thay vì crash cả batch).
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        run_config=RunConfig(timeout=180, max_retries=5, max_workers=3),
    )
    return result.to_pandas()


# =============================================================================
# A/B Comparison
# =============================================================================

# Mỗi entry: (label, pipeline_kwargs)
AB_CONFIGS: list[tuple[str, dict]] = [
    ("hybrid_rerank_cross_encoder", {"retrieval_mode": "hybrid", "use_reranking": True, "rerank_method": "cross_encoder"}),
    ("dense_only_no_rerank", {"retrieval_mode": "dense", "use_reranking": False}),
]


def _cache_path(label: str) -> Path:
    return Path(__file__).parent / f"results_{label}.csv"


def load_cached_configs(configs: list[tuple[str, dict]] = AB_CONFIGS) -> dict:
    """Load lại các config đã eval xong từ trước (results_<label>.csv trên đĩa)."""
    import pandas as pd

    cached = {}
    for label, _ in configs:
        path = _cache_path(label)
        if path.exists():
            cached[label] = pd.read_csv(path)
            logger.info("Loaded cached config '%s' from %s", label, path)
    return cached


def run_one_config(golden_dataset: list[dict], label: str, kwargs: dict) -> "pd.DataFrame":
    """
    Chạy pipeline + RAGAS eval cho 1 config, lưu ngay ra CSV (results_<label>.csv)
    rồi export results.md gộp với các config khác đã có sẵn trên đĩa (nếu có).

    Chạy độc lập từng config (thay vì cả batch) giúp: (1) không mất dữ liệu nếu 1 config
    bị lỗi/crash giữa chừng, (2) không phải chờ hết cả 2 config mới thấy kết quả.
    """
    logger.info("=== A/B config: %s (%r) ===", label, kwargs)
    dataset = run_pipeline_on_dataset(golden_dataset, **kwargs)
    df = evaluate_with_ragas(dataset)

    df.to_csv(_cache_path(label), index=False)
    logger.info("Cached config '%s' -> %s", label, _cache_path(label))

    all_results = load_cached_configs()
    all_results[label] = df  # đảm bảo bản mới nhất được dùng, không phải bản vừa đọc lại
    export_results(all_results)
    return df


def compare_configs(golden_dataset: list[dict], configs: list[tuple[str, dict]] = AB_CONFIGS) -> dict:
    """
    So sánh A/B giữa các configs (dense-only vs hybrid, rerank vs no-rerank, ...).
    Chạy tuần tự từng config qua run_one_config() — mỗi config tự cache + export riêng.

    Returns:
        {config_label: pandas.DataFrame per-row scores}
    """
    results = {}
    for label, kwargs in configs:
        results[label] = run_one_config(golden_dataset, label, kwargs)
    return results


# =============================================================================
# Export Results
# =============================================================================

METRIC_COLS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]


def _summary_table(df) -> str:
    means = df[METRIC_COLS].mean()
    lines = ["| Metric | Score |", "|--------|-------|"]
    for m in METRIC_COLS:
        lines.append(f"| {m} | {means[m]:.3f} |")
    return "\n".join(lines)


def _worst_rows(df, n: int = 3) -> str:
    df = df.copy()
    df["avg_score"] = df[METRIC_COLS].mean(axis=1)
    worst = df.sort_values("avg_score").head(n)
    lines = ["| Question | Avg Score | Faithfulness | Answer Rel. | Ctx Recall | Ctx Precision |",
             "|----------|-----------|--------------|-------------|------------|----------------|"]
    for _, row in worst.iterrows():
        q = str(row["user_input"])[:70].replace("|", "/")
        lines.append(
            f"| {q}... | {row['avg_score']:.3f} | {row['faithfulness']:.3f} | "
            f"{row['answer_relevancy']:.3f} | {row['context_recall']:.3f} | {row['context_precision']:.3f} |"
        )
    return "\n".join(lines)


def export_results(comparison: dict):
    """Export A/B evaluation results to results.md"""
    content = "# RAG Evaluation Results (RAGAS)\n\n"
    content += f"Golden dataset: {len(load_golden_dataset())} câu hỏi (easy/medium/hard, cover factual / ambiguous / complex / injection / unanswerable).\n\n"
    content += "## A/B Comparison — Overall Scores\n\n"

    content += "| Config | " + " | ".join(METRIC_COLS) + " |\n"
    content += "|--------|" + "|".join(["---"] * len(METRIC_COLS)) + "|\n"
    for label, df in comparison.items():
        means = df[METRIC_COLS].mean()
        content += f"| {label} | " + " | ".join(f"{means[m]:.3f}" for m in METRIC_COLS) + " |\n"

    for label, df in comparison.items():
        content += f"\n## Config: {label}\n\n"
        content += _summary_table(df) + "\n\n"
        content += "### Worst Performers\n\n"
        content += _worst_rows(df) + "\n"

    content += "\n## Recommendations\n\n"
    content += (
        "- So sánh 2 bảng điểm ở trên để xác định config nào tốt hơn cho từng metric.\n"
        "- Với các câu injection/unanswerable (q13-q15), faithfulness/answer_relevancy thấp "
        "là ĐÚNG NHƯ MONG ĐỢI nếu model từ chối trả lời đúng cách — không nên coi là lỗi.\n"
        "- Nếu context_precision thấp ở nhiều câu, cân nhắc giảm top_k hoặc tăng ngưỡng rerank.\n"
        "- Nếu context_recall thấp, cân nhắc tăng top_k trước rerank hoặc cải thiện chunking (Task 4).\n"
    )

    RESULTS_PATH.write_text(content, encoding="utf-8")
    logger.info("Results written to %s", RESULTS_PATH)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG evaluation (RAGAS)")
    parser.add_argument(
        "--config",
        choices=[label for label, _ in AB_CONFIGS] + ["all"],
        default="all",
        help="Chạy 1 config riêng (vd: dense_only_no_rerank) hoặc 'all' cho cả 2 tuần tự.",
    )
    args = parser.parse_args()

    golden_dataset = load_golden_dataset()
    print(f"Loaded {len(golden_dataset)} test cases")

    if args.config == "all":
        compare_configs(golden_dataset)
    else:
        kwargs = dict(AB_CONFIGS)[args.config]
        run_one_config(golden_dataset, args.config, kwargs)

    print(f"Done. See {RESULTS_PATH}")
