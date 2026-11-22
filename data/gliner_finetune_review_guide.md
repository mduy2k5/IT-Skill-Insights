# Rà soát nhãn cho thử nghiệm fine-tune GLiNER

Queue gốc `gliner_finetune_review_queue.csv` vẫn dành cho quyết định của người rà soát. Pilot trước đã dùng một lượt AI review cũ; báo cáo lịch sử là `gliner_finetune_pilot_report.md`. Lượt mở rộng bên dưới được tạo sau pilot và chưa được fine-tune.

## Tiêu chí duyệt nhãn

1. **Có bằng chứng trong job gốc.** Span phải khớp chính xác với `requirements_text` hoặc `responsibilities_text`. Với cách diễn đạt tương đương tiếng Việt/Anh, dùng một cụm thật trong mô tả làm surface và ghi đúng section; không bịa span theo tên skill.
2. **Đúng phạm vi sáu nhãn.** Gán nhãn theo loại thực thể kỹ thuật: ngôn ngữ; framework/thư viện; CSDL/query; cloud/data platform; công cụ phát triển/kiểm thử; phương pháp/protocol/kiến trúc kỹ thuật.
3. **Loại nội dung không phải skill.** Chức danh/nhóm, công ty, sản phẩm bàn giao chung, yêu cầu nghiệp vụ hoặc kỹ năng tài chính không được ép vào nhãn kỹ thuật.
4. **Không chắc thì loại khỏi positive train.** Không có span xác minh được hoặc không chọn được nhãn thì để `needs_span`/`needs_label`; section train tương ứng không dùng làm background. Không lấy dự đoán GLiNER của chính nó làm nhãn cho span bỏ sót.
5. **Ghi rõ nguồn người duyệt.** `gliner_finetune_ai_review.csv` đánh dấu `reviewer=Codex AI first-pass`; đây không phải quyết định của người dùng. `gliner_finetune_review_queue.csv` không bị thay thế.

Lượt mở rộng hiện có 633 positive/repaired rows trong review benchmark, trong đó 308/316 mục benchmark bị bỏ sót đã được AI gắn với span nguyên văn và 8 mục bị loại khỏi phạm vi. Đây vẫn là AI first pass, chưa phải gold được con người xác nhận.

## Lượt mở rộng độ phủ theo job

AI đã đối chiếu các mục benchmark GLiNER bỏ sót với toàn văn `requirements` và `responsibilities`, rồi chạy GLiNER ngưỡng thấp trên 28 section để đề xuất span chưa có trong review. Lượt này chưa chứng minh mọi skill trong mô tả đã được tìm thấy.

- `gliner_gold_missed_span_audit.csv`: từng mục benchmark bị bỏ sót, kèm surface nguyên văn, section/offset, ngữ cảnh, quyết định AI và các cột `human_decision`, `approved_*`, `notes` để người rà soát sửa.
- `gliner_job_coverage_ai_review.csv`: span mới do GLiNER đề xuất, gồm cả các lần nhắc lại, cùng quyết định AI, lý do và các cột `human_*` riêng.
- `gliner_job_coverage_report.md`: thống kê theo job/section và quy tắc tránh xem span pending là negative.
- `gliner_job_coverage_expanded_annotations.csv`: các span AI đang xem là positive; cần rà trước khi dùng như nhãn gold.

Khi xác nhận một span trong `gliner_gold_missed_span_audit.csv`, ghi quyết định vào `human_decision` và surface/section/label đã sửa vào `approved_*`. Trong `gliner_job_coverage_ai_review.csv`, dùng `human_decision` và `human_approved_*`. Nếu mô tả còn skill chưa có trong hai CSV, thêm span từ đúng section nguồn. Chỉ coi một section đã đầy đủ sau khi đã rà toàn văn; hết ứng viên GLiNER không chứng minh đã tìm hết entity. Không coi các quyết định AI này là nhãn gold.

## Cách rà soát CSV

- `candidate_kind=gold_found_candidate`: model đã tìm thấy span thuộc gold nháp. Xác nhận span và nhãn, hoặc sửa/xóa nếu sai.
- `candidate_kind=gold_missed_candidate`: gold nháp có skill nhưng model bỏ sót. Nếu đúng, xác nhận đúng cụm trong mô tả và điền nhãn GLiNER; nếu cụm không có hoặc không phải skill trong phạm vi, loại bỏ.
- `candidate_kind=model_extra_candidate`: model dự đoán một cụm ngoài gold nháp. Đánh dấu âm nếu đó không phải skill trong phạm vi; nếu thực tế là skill, xác nhận như một span dương và gán nhãn.
- `context` chứa đoạn trích quanh vị trí tìm được. `span_start_char` là offset ký tự bắt đầu, `span_end_char_exclusive` là offset kết thúc không bao gồm ký tự cuối. Đây là offset ký tự để rà soát; bộ chuyển đổi sẽ đổi sang offset token GLiNER sau khi nhãn được duyệt.
- Nếu không tìm được cụm nguyên văn, hai cột offset để trống. Mở mô tả nguồn theo `job_id`, tìm đúng span rồi điền `approved_surface`, `approved_section` và quyết định tương ứng. Không suy đoán span từ tên skill.
- Với hàng dương đã xác nhận, điền `human_decision=approve_positive` và `approved_gliner_label`. Nếu sửa, dùng `human_decision=repair`, điền `approved_surface`, `approved_section`, `approved_gliner_label`. Với ứng viên âm, dùng `human_decision=reject_background`. Nếu không thuộc phạm vi benchmark, dùng `human_decision=out_of_scope`.
- Chỉ dùng đúng một trong các nhãn: `programming language`; `software framework or library`; `database or query technology`; `cloud or data platform`; `software development or testing tool`; `technical method, protocol, or architecture`.
- Nếu phát hiện skill khác bị bỏ sót hoàn toàn, thêm hàng mới theo cùng cấu trúc, điền `job_id`, `split`, `candidate_skill`, `source_section`, `approved_surface`, `approved_gliner_label` và `human_decision=approve_positive`.

## Chia job để tránh rò rỉ giữa train và đánh giá

Toàn bộ các đoạn của một job chỉ nằm trong một split. CSV đã gán sẵn:

- `train`: 8 job — dùng để fine-tune.
- `validation`: 2 job — dùng để theo dõi và chọn cấu hình.
- `holdout_eval`: 4 job — chỉ dùng đánh giá cuối, không đưa vào train hay chọn cấu hình.

Các job holdout: `2144686`, `2143927`, `2139328`, `2141955`. Các job validation: `2143923`, `2138202`. Tập hiện chỉ có 14 job, nên kết quả fine-tune là thử nghiệm pilot và có độ bất định lớn; cần bổ sung job đã gán nhãn để kết luận chắc hơn.

### Benchmark ngoài SkillSpan

Đã tạo thêm validation `29` job và holdout `31` job từ nguồn TECH của SkillSpan trong `data/skillspan_external/`. Mỗi job giữ nguyên một split theo upstream dev/test; không có mô tả trùng chính xác giữa hai split. Bộ này có nhãn tiếng Anh `Knowledge`/`Skill`, khác taxonomy sáu nhãn kỹ thuật của dự án. Chỉ dùng `Knowledge` làm benchmark ngoài về trích xuất thực thể kỹ thuật; không coi `Skill` là negative và không dùng hai split này để fine-tune.

Đây là phép đo ngoài nguồn/ngoài ngôn ngữ, không thay thế benchmark tiếng Việt Saramin. Chi tiết provenance, giới hạn và split nằm trong [README benchmark](skillspan_external/README.md). Baseline GLiNER ở ngưỡng `0.40` đã chạy một lần; holdout cần được giữ cố định cho các vòng chọn model tiếp theo.

## Thử tỷ lệ negative sampling

Sau khi nhãn được duyệt và kiểm tra đầy đủ, chạy cùng checkpoint, cùng split, cùng seed và cùng lịch train với tỷ lệ negative entity types `0%`, `50%`, `75%`. Pilot dùng `ner_negatives` để chọn phần tương ứng trong các nhãn vắng mặt ở từng example; giữ loss-level `negatives=1.0` và `masking=none` cố định vì hai cơ chế này khác nhau trong GLiNER hiện tại. Đây là cách thử tỷ lệ có kiểm soát, không tái tạo nguyên sampler cùng-batch của paper. Dùng validation để chọn cấu hình; giữ holdout_eval cho báo cáo cuối. Báo precision, recall, F1, số FP/FN và đường cong ngưỡng trên cùng một bộ nhãn.

GLiNER paper báo cáo 0%, 50%, 75% negative entity types lần lượt đạt F1 53.3, 60.9, 58.6 trong thiết lập của paper. Vì thế 50% là một điểm thử nghiệm có căn cứ, không phải tỷ lệ tối ưu đã được xác nhận cho dữ liệu job của dự án. Tài liệu train GLiNER cũng cho phép cấu hình `negatives` và yêu cầu nhãn span theo chỉ số token, bắt đầu/kết thúc inclusive; offset ký tự trong CSV không thể đưa thẳng vào tập train.

- [Bài GLiNER tại NAACL 2024](https://aclanthology.org/2024.naacl-long.300.pdf)
- [Tài liệu huấn luyện GLiNER](https://urchade.github.io/GLiNER/training.html)

## Nguồn và phạm vi tệp

Queue này lấy các `found`/`missed` có skill nằm trong danh sách 305 từ `web/static/data/skill_benchmark_v0.json` và `data/skill_benchmark_gliner_label_filtered.md`; đồng thời đưa cả 22 `extras` của benchmark vào để rà soát ứng viên âm. Context và offset được dò nguyên văn từ `data/staging/saramin/embedded_jobs_2026-11-09.json`. Các trường `human_*` trong queue gốc còn để trống, chờ người dùng có thể sửa độc lập.

Tạo lại queue sau khi benchmark hoặc nguồn thay đổi bằng lệnh:

```powershell
python scripts/prepare_gliner_review_queue.py
```
