"""RAGAS evaluation and A/B comparison for the university-services RAG app.

Examples (run from the repository root)::

    python -m group_project.evaluation.eval_pipeline --list-configs
    python -m group_project.evaluation.eval_pipeline --limit 1 --prediction-only
    python -m group_project.evaluation.eval_pipeline
    python -m group_project.evaluation.eval_pipeline --configs dense_only_no_rerank hybrid_cross_encoder

Predictions and metric scores are checkpointed in ``evaluation/artifacts`` so an
interrupted or rate-limited run can be resumed without paying for completed calls.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Callable, Iterable

from dotenv import load_dotenv

EVALUATION_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EVALUATION_DIR.parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

GOLDEN_DATASET_PATH = EVALUATION_DIR / "golden_dataset.json"
RESULTS_PATH = EVALUATION_DIR / "results.md"
ARTIFACTS_DIR = EVALUATION_DIR / "artifacts"
PREDICTIONS_PATH = ARTIFACTS_DIR / "predictions.json"
SCORES_PATH = ARTIFACTS_DIR / "ragas_scores.json"

METRIC_NAMES = (
    "faithfulness",
    "answer_relevancy",
    "context_recall",
    "context_precision",
)
DEFAULT_JUDGE_MODEL = os.getenv("EVAL_MODEL", "google/gemini-2.5-flash-lite")


@dataclass(frozen=True)
class EvalConfig:
    name: str
    retrieval_mode: str
    use_reranking: bool
    rerank_method: str


# Kept identical to tests/test_ab_pipeline.py so QA evaluates every advertised mode.
AB_CONFIGS: tuple[EvalConfig, ...] = (
    EvalConfig("dense_only_no_rerank", "dense", False, "cross_encoder"),
    EvalConfig("hybrid_no_rerank", "hybrid", False, "cross_encoder"),
    EvalConfig("hybrid_cross_encoder", "hybrid", True, "cross_encoder"),
    EvalConfig("hybrid_mmr", "hybrid", True, "mmr"),
)


def load_golden_dataset(path: Path = GOLDEN_DATASET_PATH) -> list[dict[str, Any]]:
    """Load and validate the golden dataset."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) < 15:
        raise ValueError(f"Golden dataset must contain at least 15 rows; found {len(data)}")

    required = {"id", "question", "expected_answer", "expected_context"}
    seen_ids: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Golden row {index} is not an object")
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Golden row {index} is missing: {sorted(missing)}")
        if any(not str(item[key]).strip() for key in required):
            raise ValueError(f"Golden row {index} contains an empty required value")
        if item["id"] in seen_ids:
            raise ValueError(f"Duplicate golden id: {item['id']}")
        seen_ids.add(item["id"])
    return data


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def _resolve_generate(rag_pipeline: Any) -> Callable[..., dict[str, Any]]:
    if callable(rag_pipeline):
        return rag_pipeline
    generate = getattr(rag_pipeline, "generate_with_citation", None)
    if callable(generate):
        return generate
    raise TypeError("rag_pipeline must be callable or expose generate_with_citation()")


def _prediction_key(item_id: str, config_name: str, top_k: int) -> str:
    return f"{config_name}:{item_id}:k{top_k}"


def collect_predictions(
    rag_pipeline: Any,
    golden_dataset: list[dict[str, Any]],
    configs: Iterable[EvalConfig] = AB_CONFIGS,
    *,
    top_k: int = 5,
    cache_path: Path = PREDICTIONS_PATH,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Run every question/config pair and checkpoint generated answers/contexts."""
    generate = _resolve_generate(rag_pipeline)
    cache: dict[str, dict[str, Any]] = _read_json(cache_path, {})
    rows: list[dict[str, Any]] = []

    for config in configs:
        for position, item in enumerate(golden_dataset, 1):
            key = _prediction_key(item["id"], config.name, top_k)
            cached = cache.get(key)
            if (
                not force
                and cached
                and cached.get("question") == item["question"]
                and not cached.get("error")
            ):
                print(f"[prediction cache] {config.name} {position}/{len(golden_dataset)}")
                rows.append(cached)
                continue

            print(f"[generate] {config.name} {position}/{len(golden_dataset)}: {item['id']}")
            row: dict[str, Any] = {
                "id": item["id"],
                "config": config.name,
                "question": item["question"],
                "expected_answer": item["expected_answer"],
                "expected_context": item["expected_context"],
                "top_k": top_k,
            }
            try:
                result = generate(
                    item["question"],
                    top_k=top_k,
                    retrieval_mode=config.retrieval_mode,
                    use_reranking=config.use_reranking,
                    rerank_method=config.rerank_method,
                )
                sources = result.get("sources") or []
                row.update(
                    {
                        "answer": result.get("answer", ""),
                        "contexts": [source.get("content", "") for source in sources],
                        "source_files": [
                            source.get("metadata", {}).get("source", "unknown")
                            for source in sources
                        ],
                        "retrieval_source": result.get("retrieval_source", "unknown"),
                        "error": None,
                    }
                )
            except Exception as exc:  # preserve failures as QA evidence; continue matrix
                row.update(
                    {
                        "answer": "",
                        "contexts": [],
                        "source_files": [],
                        "retrieval_source": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

            cache[key] = row
            rows.append(row)
            _write_json(cache_path, cache)

    return rows


class LocalSentenceTransformerEmbeddings:
    """Created lazily as a RAGAS BaseRagasEmbedding subclass.

    The actual subclass is returned by :func:`build_local_embeddings`; keeping the
    adapter construction lazy lets dataset validation/tests run without importing
    the heavy RAGAS and sentence-transformers stacks.
    """


def build_local_embeddings():
    """Reuse Task 4's multilingual embedding model for answer relevancy."""
    from ragas.embeddings.base import BaseRagasEmbedding
    from src.task4_chunking_indexing import _IS_E5_MODEL, get_embedding_model

    model = get_embedding_model()

    class _Adapter(BaseRagasEmbedding):
        def _prepare(self, text: str) -> str:
            return f"query: {text}" if _IS_E5_MODEL else text

        def embed_text(self, text: str, **kwargs: Any) -> list[float]:
            vector = model.encode(self._prepare(text), normalize_embeddings=True)
            return vector.tolist()

        async def aembed_text(self, text: str, **kwargs: Any) -> list[float]:
            return await asyncio.to_thread(self.embed_text, text, **kwargs)

        def embed_texts(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
            prepared = [self._prepare(text) for text in texts]
            vectors = model.encode(prepared, normalize_embeddings=True)
            return vectors.tolist()

        async def aembed_texts(
            self, texts: list[str], **kwargs: Any
        ) -> list[list[float]]:
            return await asyncio.to_thread(self.embed_texts, texts, **kwargs)

    return _Adapter()


def build_ragas_metrics(
    judge_model: str,
    strictness: int = 1,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Create RAGAS 0.4 metrics using the project's OpenRouter credentials."""
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextPrecision,
        ContextRecall,
        Faithfulness,
    )

    api_key = os.getenv("OPEN_ROUTER_API") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPEN_ROUTER_API (or OPENAI_API_KEY) is not set")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=90.0,
        max_retries=2,
    )
    # RAGAS prompts request structured JSON. Reasoning models may spend a large
    # part of the completion budget before emitting that JSON, so the usual chat
    # default (often 1K tokens) produces IncompleteOutputException.
    judge = llm_factory(
        judge_model,
        provider="openai",
        client=client,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    embeddings = build_local_embeddings()
    return {
        "faithfulness": Faithfulness(llm=judge),
        "answer_relevancy": AnswerRelevancy(
            llm=judge, embeddings=embeddings, strictness=strictness
        ),
        "context_recall": ContextRecall(llm=judge),
        "context_precision": ContextPrecision(llm=judge),
    }


async def _score_one(metric_name: str, metric: Any, row: dict[str, Any]) -> float:
    common = {"user_input": row["question"]}
    if metric_name == "faithfulness":
        result = await metric.ascore(
            **common,
            response=row["answer"],
            retrieved_contexts=row["contexts"],
        )
    elif metric_name == "answer_relevancy":
        result = await metric.ascore(**common, response=row["answer"])
    elif metric_name in {"context_recall", "context_precision"}:
        result = await metric.ascore(
            **common,
            reference=row["expected_answer"],
            retrieved_contexts=row["contexts"],
        )
    else:  # defensive guard for future additions
        raise ValueError(f"Unknown metric: {metric_name}")
    return float(result.value)


async def score_predictions(
    predictions: list[dict[str, Any]],
    *,
    judge_model: str,
    strictness: int = 1,
    max_tokens: int = 8192,
    cache_path: Path = SCORES_PATH,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Score predictions sequentially and checkpoint each individual metric."""
    metrics = build_ragas_metrics(
        judge_model, strictness=strictness, max_tokens=max_tokens
    )
    cache: dict[str, dict[str, Any]] = _read_json(cache_path, {})
    output: list[dict[str, Any]] = []

    for position, prediction in enumerate(predictions, 1):
        key = (
            f"{_prediction_key(prediction['id'], prediction['config'], prediction['top_k'])}"
            f":judge={judge_model}:strictness={strictness}"
        )
        saved = cache.get(key, {"metrics": {}, "metric_errors": {}})
        completed_metrics = dict(saved.get("metrics", {}))
        scored = {**prediction, **completed_metrics}
        metric_errors = dict(saved.get("metric_errors", {}))

        if prediction.get("error") or not prediction.get("contexts") or not prediction.get("answer"):
            reason = prediction.get("error") or "Empty answer or retrieval context"
            for name in METRIC_NAMES:
                scored[name] = None
                metric_errors[name] = reason
            output.append({**scored, "metric_errors": metric_errors})
            continue

        pending: list[tuple[str, Any]] = []
        for name, metric in metrics.items():
            if not force and name in completed_metrics:
                print(f"[RAGAS cache] {position}/{len(predictions)} {name}")
                scored[name] = completed_metrics[name]
                continue

            print(f"[RAGAS] {position}/{len(predictions)} {prediction['config']} {prediction['id']} {name}")
            pending.append((name, metric))

        # Metrics are independent. Evaluate the missing metrics concurrently for
        # one row, then checkpoint that row before moving to the next one.
        values = await asyncio.gather(
            *(_score_one(name, metric, prediction) for name, metric in pending),
            return_exceptions=True,
        )
        for (name, _metric), value in zip(pending, values):
            try:
                if isinstance(value, BaseException):
                    raise value
                scored[name] = None if math.isnan(value) else value
                if scored[name] is not None:
                    completed_metrics[name] = scored[name]
                    metric_errors.pop(name, None)
                else:
                    metric_errors[name] = "RAGAS returned NaN"
            except Exception as exc:  # continue so failures are visible in results.md
                scored[name] = None
                metric_errors[name] = f"{type(exc).__name__}: {exc}"

        saved = {
            "metrics": completed_metrics,
            "metric_errors": metric_errors,
        }
        cache[key] = saved
        _write_json(cache_path, cache)

        output.append({**scored, "metric_errors": metric_errors})

    return output


def _mean(values: Iterable[Any]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return fmean(numeric) if numeric else None


def summarize(rows: list[dict[str, Any]], config: EvalConfig) -> dict[str, Any]:
    config_rows = [row for row in rows if row["config"] == config.name]
    metric_means = {name: _mean(row.get(name) for row in config_rows) for name in METRIC_NAMES}
    overall = _mean(metric_means.values())
    return {
        "config": asdict(config),
        "count": len(config_rows),
        "successful_predictions": sum(not row.get("error") for row in config_rows),
        "fully_scored": sum(
            all(isinstance(row.get(name), (int, float)) for name in METRIC_NAMES)
            for row in config_rows
        ),
        "metrics": metric_means,
        "average": overall,
    }


def evaluate_with_ragas(
    rag_pipeline: Any,
    golden_dataset: list[dict[str, Any]],
    config: EvalConfig = AB_CONFIGS[0],
    *,
    top_k: int = 5,
    judge_model: str | None = None,
    strictness: int = 1,
    max_tokens: int = 8192,
    force: bool = False,
) -> dict[str, Any]:
    """Evaluate one pipeline configuration with four RAGAS metrics."""
    judge_model = judge_model or DEFAULT_JUDGE_MODEL
    if not judge_model:
        raise RuntimeError("Set EVAL_MODEL or CHAT_MODEL before running RAGAS")
    predictions = collect_predictions(
        rag_pipeline, golden_dataset, [config], top_k=top_k, force=force
    )
    rows = asyncio.run(
        score_predictions(
            predictions,
            judge_model=judge_model,
            strictness=strictness,
            max_tokens=max_tokens,
            force=force,
        )
    )
    return {"summary": summarize(rows, config), "rows": rows}


def compare_configs(
    rag_pipeline: Any,
    golden_dataset: list[dict[str, Any]],
    configs: Iterable[EvalConfig] = AB_CONFIGS,
    *,
    top_k: int = 5,
    judge_model: str | None = None,
    strictness: int = 1,
    max_tokens: int = 8192,
    force: bool = False,
    prediction_only: bool = False,
) -> dict[str, Any]:
    """Run the complete A/B matrix and return row-level plus aggregate results."""
    selected = tuple(configs)
    predictions = collect_predictions(
        rag_pipeline, golden_dataset, selected, top_k=top_k, force=force
    )
    if prediction_only:
        rows = predictions
    else:
        judge_model = judge_model or DEFAULT_JUDGE_MODEL
        if not judge_model:
            raise RuntimeError("Set EVAL_MODEL or CHAT_MODEL before running RAGAS")
        rows = asyncio.run(
            score_predictions(
                predictions,
                judge_model=judge_model,
                strictness=strictness,
                max_tokens=max_tokens,
                force=force,
            )
        )

    return {
        "framework": "RAGAS 0.4.x",
        "judge_model": None if prediction_only else judge_model,
        "answer_relevancy_strictness": strictness,
        "judge_max_tokens": max_tokens,
        "top_k": top_k,
        "dataset_size": len(golden_dataset),
        "summaries": {config.name: summarize(rows, config) for config in selected},
        "rows": rows,
    }


def _format_score(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "N/A"


def _row_average(row: dict[str, Any]) -> float | None:
    return _mean(row.get(name) for name in METRIC_NAMES)


def _failure_diagnosis(row: dict[str, Any]) -> tuple[str, str]:
    if row.get("error"):
        return "Pipeline", row["error"]
    available = {name: row.get(name) for name in METRIC_NAMES if isinstance(row.get(name), (int, float))}
    if not available:
        errors = row.get("metric_errors") or {}
        return "Evaluation", next(iter(errors.values()), "Không có điểm RAGAS hợp lệ")
    weakest_value = min(available.values())
    # Prefer the upstream retrieval diagnosis when retrieval and generation
    # metrics tie at the minimum: missing evidence commonly causes both.
    if available.get("context_recall") == weakest_value:
        return "Retrieval", "Retriever bỏ sót một phần evidence trong đáp án chuẩn"
    if available.get("context_precision") == weakest_value:
        return "Retrieval/reranking", "Các chunk liên quan chưa được ưu tiên đủ cao"
    weakest = min(available, key=available.get)
    if weakest == "faithfulness":
        return "Generation", "Một số khẳng định trong câu trả lời chưa được context hỗ trợ"
    return "Generation", "Câu trả lời chưa tập trung đầy đủ vào ý định câu hỏi"


def export_results(results: dict[str, Any], path: Path = RESULTS_PATH) -> None:
    """Write a reproducible Markdown report without inventing missing scores."""
    summaries = results["summaries"]
    rows = results["rows"]
    config_names = list(summaries)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    lines = [
        "# RAG Evaluation Results",
        "",
        "## Thiết lập",
        "",
        f"- Framework: {results['framework']}",
        f"- Judge model: `{results.get('judge_model') or 'chưa chạy RAGAS'}`",
        f"- Golden dataset: {results['dataset_size']} câu hỏi",
        f"- Configs: {', '.join(f'`{name}`' for name in config_names)}",
        f"- `top_k`: {results['top_k']}",
        f"- Answer relevancy strictness: {results['answer_relevancy_strictness']}",
        f"- Judge max tokens: {results['judge_max_tokens']}",
        f"- Thời điểm chạy: {generated_at}",
        "",
        "## Smoke test bốn mode trong `tests/test_ab_pipeline.py`",
        "",
        "| Config | Retrieval | Reranking | Status | Contexts |",
        "|---|---|---|---|---:|",
    ]
    prediction_cache = _read_json(PREDICTIONS_PATH, {})
    first_id = rows[0]["id"] if rows else ""
    for config in AB_CONFIGS:
        smoke = prediction_cache.get(
            _prediction_key(first_id, config.name, results["top_k"]), {}
        )
        status = "PASS" if smoke and not smoke.get("error") else "FAIL"
        context_count = len(smoke.get("contexts", [])) if smoke else 0
        reranking = config.rerank_method if config.use_reranking else "off"
        lines.append(
            f"| `{config.name}` | {config.retrieval_mode} | {reranking} | "
            f"{status} | {context_count} |"
        )

    lines.extend([
        "",
        "## Điểm tổng hợp",
        "",
        "| Config | Faithfulness | Answer relevance | Context recall | Context precision | Average | Scored |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for name, summary in summaries.items():
        metrics = summary["metrics"]
        lines.append(
            f"| `{name}` | {_format_score(metrics['faithfulness'])} | "
            f"{_format_score(metrics['answer_relevancy'])} | "
            f"{_format_score(metrics['context_recall'])} | "
            f"{_format_score(metrics['context_precision'])} | "
            f"{_format_score(summary['average'])} | "
            f"{summary['fully_scored']}/{summary['count']} |"
        )

    ranked = [summary for summary in summaries.values() if summary["average"] is not None]
    lines.extend(["", "## Phân tích A/B", ""])
    if ranked:
        ranked.sort(key=lambda item: item["average"], reverse=True)
        best = ranked[0]
        lines.append(
            f"Config có điểm trung bình cao nhất là `{best['config']['name']}` "
            f"({_format_score(best['average'])}). Kết luận chỉ dựa trên các hàng đã chấm "
            "thành công; xem cột Scored trước khi khái quát hóa."
        )
        if len(ranked) > 1:
            runner_up = ranked[1]
            delta = best["average"] - runner_up["average"]
            metric_deltas = {
                name: best["metrics"][name] - runner_up["metrics"][name]
                for name in METRIC_NAMES
                if best["metrics"][name] is not None
                and runner_up["metrics"][name] is not None
            }
            gains = [name for name, value in metric_deltas.items() if value > 0]
            losses = [name for name, value in metric_deltas.items() if value < 0]
            lines.append(
                f"Chênh lệch average so với `{runner_up['config']['name']}` là "
                f"{delta:+.3f}. Config thắng tốt hơn ở {', '.join(gains) or 'không có metric nào'}, "
                f"nhưng kém hơn ở {', '.join(losses) or 'không có metric nào'}."
            )
    else:
        lines.append("Chưa có điểm RAGAS hợp lệ; không đưa ra kết luận A/B.")

    lines.extend(["", "## Worst performers (bottom 3)", ""])
    scored_rows = [row for row in rows if _row_average(row) is not None]
    scored_rows.sort(key=lambda row: _row_average(row) or 0.0)
    lines.extend(
        [
            "| # | Config | Question | Faithfulness | Relevance | Recall | Precision | Average | Failure stage | Root cause |",
            "|---:|---|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    if scored_rows:
        for rank, row in enumerate(scored_rows[:3], 1):
            stage, cause = _failure_diagnosis(row)
            question = row["question"].replace("|", "\\|")
            lines.append(
                f"| {rank} | `{row['config']}` | {question} | "
                f"{_format_score(row.get('faithfulness'))} | "
                f"{_format_score(row.get('answer_relevancy'))} | "
                f"{_format_score(row.get('context_recall'))} | "
                f"{_format_score(row.get('context_precision'))} | "
                f"{_format_score(_row_average(row))} | {stage} | {cause} |"
            )
    else:
        lines.append(
            "| 1 | N/A | Chưa có hàng được chấm thành công | N/A | N/A | "
            "N/A | N/A | N/A | Evaluation | Xem lỗi bên dưới |"
        )

    failures = [
        row
        for row in rows
        if row.get("error") or any(row.get(name) is None for name in METRIC_NAMES)
    ]
    lines.extend(["", "## Lỗi và dữ liệu thiếu", ""])
    if failures:
        lines.append(f"Có {len(failures)}/{len(rows)} hàng chưa có đủ bốn metric.")
        lines.append("")
        for row in failures[:10]:
            errors = row.get("metric_errors") or {}
            detail = row.get("error") or "; ".join(
                f"{name}: {message}" for name, message in errors.items()
            )
            lines.append(f"- `{row['config']}/{row['id']}`: {detail}")
        if len(failures) > 10:
            lines.append(f"- … và {len(failures) - 10} hàng khác; xem `artifacts/ragas_scores.json`.")
    else:
        lines.append("Không có lỗi; mọi hàng đều có đủ bốn metric.")

    lines.extend(
        [
            "",
            "## Khuyến nghị",
            "",
            "1. Ưu tiên config có context recall/precision cao nhất, rồi kiểm tra thủ công các citation của bottom 3 trước khi chọn cấu hình production.",
            "2. Tách chunk theo tiêu đề/mục chính sách và dùng cùng một chunk size cho dense và BM25 để RRF không hợp nhất các đơn vị nội dung lệch nhau.",
            "3. Giữ cache dự đoán và điểm số; khi rate limit xảy ra, chạy lại cùng lệnh để tiếp tục các metric còn thiếu thay vì tạo lại toàn bộ đáp án.",
            "",
            "## Tái lập",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -m group_project.evaluation.eval_pipeline",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _select_configs(names: list[str] | None) -> tuple[EvalConfig, ...]:
    if not names:
        return AB_CONFIGS
    by_name = {config.name: config for config in AB_CONFIGS}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        raise ValueError(f"Unknown configs: {', '.join(unknown)}")
    return tuple(by_name[name] for name in names)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAGAS A/B evaluation pipeline")
    parser.add_argument("--configs", nargs="+", choices=[c.name for c in AB_CONFIGS])
    parser.add_argument("--limit", type=int, help="Evaluate only the first N golden rows")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--strictness", type=int, default=1, help="Answer relevancy generations per row")
    parser.add_argument("--judge-max-tokens", type=int, default=8192)
    parser.add_argument("--prediction-only", action="store_true", help="Run RAG generation but skip judge calls")
    parser.add_argument("--force", action="store_true", help="Ignore prediction and score caches")
    parser.add_argument("--list-configs", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_configs:
        for config in AB_CONFIGS:
            print(
                f"{config.name}: retrieval={config.retrieval_mode}, "
                f"rerank={config.use_reranking}, method={config.rerank_method}"
            )
        return 0
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    if args.top_k < 1:
        raise ValueError("--top-k must be at least 1")
    if args.strictness < 1:
        raise ValueError("--strictness must be at least 1")
    if args.judge_max_tokens < 256:
        raise ValueError("--judge-max-tokens must be at least 256")

    golden = load_golden_dataset()
    if args.limit:
        golden = golden[: args.limit]
    configs = _select_configs(args.configs)

    from src.task10_generation import generate_with_citation

    results = compare_configs(
        generate_with_citation,
        golden,
        configs,
        top_k=args.top_k,
        judge_model=args.judge_model,
        strictness=args.strictness,
        max_tokens=args.judge_max_tokens,
        force=args.force,
        prediction_only=args.prediction_only,
    )
    export_results(results)
    print(f"Wrote {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
