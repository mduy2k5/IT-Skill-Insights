# Kiểm toán độ phủ skill theo job (AI first pass)

> Đây là lượt AI rà soát ứng viên do GLiNER đề xuất, chưa phải nhãn người xác nhận. Mô hình chỉ tạo danh sách ứng viên; các quyết định `approve`/`reject` dựa trên rule taxonomy và ngữ cảnh job, không lấy score làm nhãn chuẩn.

## Tổng quan

- Job đã quét: `14`; section có nội dung: `28`.
- Span GLiNER chưa có trong review trước: `159` (gộp theo vị trí span, gộp các nhãn dự đoán trùng span).
- Lượt AI review mới, gồm cả các lần nhắc lặp lại của skill đã duyệt: `180`.
- Kết quả: `{'reject_background': 45, 'approve_repeat_positive': 22, 'out_of_scope': 48, 'approve_positive': 65}`.
- Model tạo `583` proposal tổng cộng ở threshold `0.15`; `168` proposal chưa được review trước, trong đó `43` đạt `0.40`. Threshold thấp chỉ dùng để mở rộng danh sách ứng viên, không dùng làm quyết định nhãn.
- Queue benchmark có `316` mục GLiNER từng bỏ sót; `308` mục được AI gắn với span nguyên văn trong job, `8` mục bị loại khỏi phạm vi, `0` mục còn thiếu quyết định/span.
- Lượt này vẫn là AI first pass: ứng viên đến từ benchmark cũ và dự đoán GLiNER ở ngưỡng thấp. Nó không chứng minh rằng mọi skill trong toàn bộ mô tả đã được tìm thấy.

## Các skill benchmark bị bỏ sót: span nguồn đã đối chiếu

Span tiếng Việt/tiếng Anh tương đương được ghi theo đúng vị trí nguyên văn trong section nguồn. Các mục cùng trỏ vào một span được giữ để rà soát, nhưng bộ chuyển đổi train sẽ gộp span trùng cùng nhãn.

| Job | Section cuối | Đã gắn span | Ngoài phạm vi | Còn cần xử lý |
|---|---|---:|---:|---:|
| `2142369` Data Engineer at DATATYK CO., LTD | requirements | 2 | 2 | 0 |
| `2142369` Data Engineer at DATATYK CO., LTD | responsibilities | 8 | 0 | 0 |
| `2139159` Tester | responsibilities | 7 | 0 | 0 |
| `2138202` Kỹ Sư Dữ Liệu (Data Engineer) | requirements | 7 | 0 | 0 |
| `2138202` Kỹ Sư Dữ Liệu (Data Engineer) | responsibilities | 1 | 0 | 0 |
| `2144836` Data Engineer (Big Data / Lakehouse) | requirements | 14 | 0 | 0 |
| `2144836` Data Engineer (Big Data / Lakehouse) | responsibilities | 6 | 0 | 0 |
| `2141955` Remote Data Engineer - AI Data Platform Japan (Python) | requirements | 19 | 0 | 0 |
| `2141955` Remote Data Engineer - AI Data Platform Japan (Python) | responsibilities | 12 | 0 | 0 |
| `2139328` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | requirements | 3 | 0 | 0 |
| `2139328` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | responsibilities | 7 | 0 | 0 |
| `2138374` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior) | requirements | 3 | 0 | 0 |
| `2138374` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior) | responsibilities | 27 | 0 | 0 |
| `2143923` Data Services Specialist | requirements | 14 | 0 | 0 |
| `2143923` Data Services Specialist | responsibilities | 8 | 0 | 0 |
| `2143927` Senior Data Services Consultant | requirements | 42 | 0 | 0 |
| `2143927` Senior Data Services Consultant | responsibilities | 33 | 0 | 0 |
| `2144784` Data Engineer/ Senior Data Engineer | requirements | 9 | 0 | 0 |
| `2144784` Data Engineer/ Senior Data Engineer | responsibilities | 9 | 0 | 0 |
| `2139603` Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689) | requirements | 9 | 1 | 0 |
| `2139603` Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689) | responsibilities | 5 | 0 | 0 |
| `2143574` Kỹ sư dữ liệu (Data Engineer) | requirements | 11 | 0 | 0 |
| `2143574` Kỹ sư dữ liệu (Data Engineer) | responsibilities | 13 | 0 | 0 |
| `2144325` Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM | requirements | 13 | 0 | 0 |
| `2144325` Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM | responsibilities | 9 | 0 | 0 |
| `2144686` AI QUANTITATIVE RESEARCHER INTERN (On-site) | requirements | 9 | 3 | 0 |
| `2144686` AI QUANTITATIVE RESEARCHER INTERN (On-site) | responsibilities | 8 | 2 | 0 |

## Theo từng job/section

| Job | Section | Repeat positive | New positive | Rejected/out of scope | Needs review |
|---|---|---:|---:|---:|---:|
| `2142369` Data Engineer at DATATYK CO., LTD | requirements | 0 | 1 | 2 | 0 |
| `2142369` Data Engineer at DATATYK CO., LTD | responsibilities | 0 | 4 | 1 | 0 |
| `2139159` Tester | requirements | 0 | 0 | 1 | 0 |
| `2139159` Tester | responsibilities | 0 | 0 | 1 | 0 |
| `2138202` Kỹ Sư Dữ Liệu (Data Engineer) | requirements | 0 | 0 | 7 | 0 |
| `2138202` Kỹ Sư Dữ Liệu (Data Engineer) | responsibilities | 0 | 1 | 3 | 0 |
| `2144836` Data Engineer (Big Data / Lakehouse) | requirements | 0 | 3 | 0 | 0 |
| `2144836` Data Engineer (Big Data / Lakehouse) | responsibilities | 0 | 1 | 5 | 0 |
| `2141955` Remote Data Engineer - AI Data Platform Japan (Python) | requirements | 0 | 3 | 9 | 0 |
| `2141955` Remote Data Engineer - AI Data Platform Japan (Python) | responsibilities | 0 | 5 | 12 | 0 |
| `2139328` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | requirements | 2 | 0 | 0 | 0 |
| `2139328` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | responsibilities | 5 | 1 | 0 | 0 |
| `2138374` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior) | requirements | 2 | 0 | 0 | 0 |
| `2138374` [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior) | responsibilities | 0 | 2 | 6 | 0 |
| `2143923` Data Services Specialist | requirements | 1 | 2 | 4 | 0 |
| `2143923` Data Services Specialist | responsibilities | 0 | 2 | 1 | 0 |
| `2143927` Senior Data Services Consultant | requirements | 2 | 10 | 13 | 0 |
| `2143927` Senior Data Services Consultant | responsibilities | 1 | 12 | 7 | 0 |
| `2144784` Data Engineer/ Senior Data Engineer | requirements | 1 | 2 | 0 | 0 |
| `2144784` Data Engineer/ Senior Data Engineer | responsibilities | 0 | 0 | 1 | 0 |
| `2139603` Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689) | requirements | 5 | 0 | 3 | 0 |
| `2139603` Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689) | responsibilities | 0 | 5 | 2 | 0 |
| `2143574` Kỹ sư dữ liệu (Data Engineer) | requirements | 0 | 1 | 3 | 0 |
| `2143574` Kỹ sư dữ liệu (Data Engineer) | responsibilities | 2 | 0 | 4 | 0 |
| `2144325` Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM | requirements | 1 | 1 | 4 | 0 |
| `2144325` Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM | responsibilities | 0 | 1 | 1 | 0 |
| `2144686` AI QUANTITATIVE RESEARCHER INTERN (On-site) | requirements | 0 | 8 | 1 | 0 |
| `2144686` AI QUANTITATIVE RESEARCHER INTERN (On-site) | responsibilities | 0 | 0 | 2 | 0 |

## Quy tắc tránh false negative

Không coi mọi token chưa được gán là negative. Chỉ lấy positive span đã duyệt; chunk giao với `needs_review`/`needs_span` phải bị loại khỏi train. Vì GLiNER chỉ đề xuất ứng viên, một section không còn ứng viên pending vẫn chưa đồng nghĩa là exhaustive gold; cần rà toàn văn độc lập trước khi dùng train negatives để kết luận về chất lượng fine-tune.

## Tệp

- Review đầy đủ: `data/gliner_job_coverage_ai_review.csv`
- Positive annotations mở rộng: `data/gliner_job_coverage_expanded_annotations.csv`
- Đối chiếu các mục benchmark GLiNER bỏ sót: `data/gliner_gold_missed_span_audit.csv`
- Prediction audit thô: `data/gliner_job_coverage_predictions.csv`
