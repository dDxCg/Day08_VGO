# RAG Evaluation Results

## Thiết lập

- Framework: RAGAS 0.4.x
- Judge model: `google/gemini-2.5-flash-lite`
- Golden dataset: 15 câu hỏi
- Configs: `dense_only_no_rerank`, `hybrid_no_rerank`
- `top_k`: 3
- Answer relevancy strictness: 1
- Judge max tokens: 4096
- Thời điểm chạy: 2026-08-04T12:00:12+07:00

## Smoke test bốn mode trong `tests/test_ab_pipeline.py`

| Config | Retrieval | Reranking | Status | Contexts |
|---|---|---|---|---:|
| `dense_only_no_rerank` | dense | off | PASS | 3 |
| `hybrid_no_rerank` | hybrid | off | PASS | 3 |
| `hybrid_cross_encoder` | hybrid | cross_encoder | PASS | 3 |
| `hybrid_mmr` | hybrid | mmr | PASS | 3 |

## Điểm tổng hợp

| Config | Faithfulness | Answer relevance | Context recall | Context precision | Average | Scored |
|---|---:|---:|---:|---:|---:|---:|
| `dense_only_no_rerank` | 0.879 | 0.592 | 0.533 | 0.528 | 0.633 | 15/15 |
| `hybrid_no_rerank` | 0.989 | 0.533 | 0.433 | 0.478 | 0.608 | 15/15 |

## Phân tích A/B

Config có điểm trung bình cao nhất là `dense_only_no_rerank` (0.633). Kết luận chỉ dựa trên các hàng đã chấm thành công; xem cột Scored trước khi khái quát hóa.
Chênh lệch average so với `hybrid_no_rerank` là +0.025. Config thắng tốt hơn ở answer_relevancy, context_recall, context_precision, nhưng kém hơn ở faithfulness.

## Worst performers (bottom 3)

| # | Config | Question | Faithfulness | Relevance | Recall | Precision | Average | Failure stage | Root cause |
|---:|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | `dense_only_no_rerank` | Người nhận học bổng RMIT được đi trao đổi và bảo lưu tối đa bao lâu? | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | Retrieval | Retriever bỏ sót một phần evidence trong đáp án chuẩn |
| 2 | `dense_only_no_rerank` | Sinh viên nộp đơn special consideration bằng cách nào và nhận kết quả ở đâu? | 1.000 | 0.000 | 0.000 | 0.000 | 0.250 | Retrieval | Retriever bỏ sót một phần evidence trong đáp án chuẩn |
| 3 | `hybrid_no_rerank` | Phí hành chính khi đóng học phí trễ hạn tại RMIT Việt Nam là bao nhiêu? | 1.000 | 0.000 | 0.000 | 0.000 | 0.250 | Retrieval | Retriever bỏ sót một phần evidence trong đáp án chuẩn |

## Lỗi và dữ liệu thiếu

Không có lỗi; mọi hàng đều có đủ bốn metric.

## Khuyến nghị

1. Ưu tiên config có context recall/precision cao nhất, rồi kiểm tra thủ công các citation của bottom 3 trước khi chọn cấu hình production.
2. Tách chunk theo tiêu đề/mục chính sách và dùng cùng một chunk size cho dense và BM25 để RRF không hợp nhất các đơn vị nội dung lệch nhau.
3. Giữ cache dự đoán và điểm số; khi rate limit xảy ra, chạy lại cùng lệnh để tiếp tục các metric còn thiếu thay vì tạo lại toàn bộ đáp án.

## Tái lập

```powershell
.\.venv\Scripts\python.exe -m group_project.evaluation.eval_pipeline
```
