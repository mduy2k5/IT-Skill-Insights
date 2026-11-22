# GLiNER fine-tuning pilot (AI first-pass review)

> **Kết quả thăm dò, chưa phải đánh giá chuẩn.** Train annotations do Codex AI rà soát từ candidate queue; đây không phải nhãn do con người xác nhận. Validation/holdout vẫn được chấm theo benchmark nháp hiện có.

- Checkpoint: `urchade/gliner_multi-v2.1`
- Runtime: GLiNER `0.2.30`, PyTorch `2.15.0+cu132`, Transformers `5.22.2`, CUDA `13.2` on `NVIDIA GeForce RTX 4050 Laptop GPU`.
- Seed: `41`; steps mỗi cấu hình: `20`; ngưỡng đánh giá: `0.40`.
- Mixed precision: `bf16`.
- Train/validation/holdout jobs: 8/2/4; nhãn dương AI-reviewed trong toàn queue: `609`; train labels: cloud or data platform, database or query technology, programming language, software development or testing tool, software framework or library, technical method, protocol, or architecture.
- Usable chunks: train `44`, validation `10`, holdout `46`.
- Source sections trong train bị bỏ toàn bộ vì còn candidate không xác minh được span: `0`; chunks có span mơ hồ: `0`; span lệch token/quá dài: `0`.
- AI-review decisions: `{'approve_positive': 513, 'repair_positive': 96, 'out_of_scope': 15, 'reject_background': 7, 'needs_span': 28}`.
- Negative-type sampling thực nghiệm: `0.00`, `0.50`, `0.75`; mỗi example nhận phần tương ứng của các nhãn train vắng mặt qua `ner_negatives`. Đây là cách vận hành để so sánh các tỷ lệ, không tái tạo nguyên sampler cùng-batch trong paper. Loss-level `negatives=1.0` và `masking=none` được giữ cố định; chúng khác với negative entity-type sampling.

## Baseline

- Validation: P=0.932, R=0.603, F1=0.732 (TP=41, FP=3, FN=27)
- Holdout: P=0.762, R=0.368, F1=0.496 (TP=64, FP=20, FN=110)

## Kết quả từng tỷ lệ

| Negative types | Validation | Holdout |
|---:|---|---|
| 0% | P=0.667, R=0.735, F1=0.699 (TP=50, FP=25, FN=18) | P=0.546, R=0.546, F1=0.546 (TP=95, FP=79, FN=79) |
| 50% | P=0.573, R=0.750, F1=0.650 (TP=51, FP=38, FN=17) | P=0.397, R=0.529, F1=0.453 (TP=92, FP=140, FN=82) |
| 75% | P=0.597, R=0.676, F1=0.634 (TP=46, FP=31, FN=22) | P=0.453, R=0.494, F1=0.473 (TP=86, FP=104, FN=88) |

Fine-tune có F1 validation cao nhất: **0%**, F1=`0.699`, vẫn thấp hơn baseline `0.732`. Không cấu hình fine-tune nào vượt baseline trên validation, nên checkpoint gốc được giữ tại `.tmp/gliner_finetune_pilot/selected_by_validation`.

## Giới hạn

1. 14 job là tập quá nhỏ cho kết luận tổng quát; validation chỉ có 2 job.
2. Annotation train do AI rà soát theo rubric, chưa có người xác nhận; một số span dịch nghĩa hoặc thiếu vị trí cụ thể bị loại và section tương ứng không được dùng train.
3. Validation/holdout dùng benchmark `draft_single_annotator`; độ chính xác của metric bị giới hạn bởi chất lượng benchmark.
4. Đây là pilot nhỏ với 20 bước mỗi cấu hình; cần thêm job và lượt review độc lập trước khi chọn checkpoint cho MVP.

Tham khảo: [GLiNER paper, mục negative entity sampling](https://aclanthology.org/2024.naacl-long.300.pdf); [tài liệu train GLiNER](https://urchade.github.io/GLiNER/training.html).

## Benchmark ngoài SkillSpan (đánh giá riêng, 2026-11-19)

Đã bổ sung một tập độc lập tiếng Anh từ SkillSpan TECH: `29` job validation, `31` job holdout; mỗi job được giữ nguyên trong một split theo upstream dev/test. Đây là phép đo ngoài nguồn/ngoài ngôn ngữ, không thay thế benchmark Saramin tiếng Việt và không được dùng làm train/negative labels. Xem [README, split manifest và provenance](skillspan_external/README.md).

Với GLiNER `urchade/gliner_multi-v2.1`, ngưỡng cố định `0.40`, sáu nhãn kỹ thuật của dự án được gộp thành một lớp và chấm exact span với nhãn `Knowledge` của SkillSpan (không coi `Skill` là negative):

| Split | Jobs | P | R | F1 | TP | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Validation | 29 | 0.510 | 0.336 | 0.405 | 271 | 260 | 535 |
| Holdout | 31 | 0.588 | 0.336 | 0.428 | 271 | 190 | 535 |

Holdout đã được chấm một lần ở ngưỡng đã định trước `0.40`; giữ nó cố định trong các vòng chọn model sau. Để đánh giá MVP tiếng Việt, vẫn cần thêm job Saramin hoặc nguồn tiếng Việt được phép lưu và phân tích, rồi gán nhãn đầy đủ theo sáu loại của dự án.
