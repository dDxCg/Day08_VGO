# RAG Evaluation Results (RAGAS)

Golden dataset: 15 câu hỏi (easy/medium/hard, cover factual / ambiguous / complex / injection / unanswerable).

## A/B Comparison — Overall Scores

| Config | faithfulness | answer_relevancy | context_recall | context_precision |
|--------|---|---|---|---|
| dense_only_no_rerank | 0.700 | nan | 0.533 | 0.495 |

## Config: dense_only_no_rerank

| Metric | Score |
|--------|-------|
| faithfulness | 0.700 |
| answer_relevancy | nan |
| context_recall | 0.533 |
| context_precision | 0.495 |

### Worst Performers

| Question | Avg Score | Faithfulness | Answer Rel. | Ctx Recall | Ctx Precision |
|----------|-----------|--------------|-------------|------------|----------------|
| Ai là diễn giả chính (keynote speaker) tại Higher Education Horizons 2... | 0.000 | 0.000 | nan | 0.000 | 0.000 |
| Sinh viên nào của RMIT Vietnam đã đại diện Việt Nam tại International ... | 0.000 | 0.000 | nan | 0.000 | 0.000 |
| RMIT Vietnam có bao nhiêu sinh viên quốc tế theo học ngành Business tr... | 0.000 | 0.000 | nan | 0.000 | nan |

## Recommendations

- So sánh 2 bảng điểm ở trên để xác định config nào tốt hơn cho từng metric.
- Với các câu injection/unanswerable (q13-q15), faithfulness/answer_relevancy thấp là ĐÚNG NHƯ MONG ĐỢI nếu model từ chối trả lời đúng cách — không nên coi là lỗi.
- Nếu context_precision thấp ở nhiều câu, cân nhắc giảm top_k hoặc tăng ngưỡng rerank.
- Nếu context_recall thấp, cân nhắc tăng top_k trước rerank hoặc cải thiện chunking (Task 4).
