# Kế hoạch crawler việc làm đa nguồn — Scrapy

**Cập nhật:** 2026-11-09  
**Quyết định kỹ thuật:** Dùng Scrapy cho crawler hiện tại và mọi adapter nguồn mới. Không tạo runtime Crawlee song song và không chuyển framework crawler.

## 1. Mục tiêu và lựa chọn kỹ thuật

Mở rộng crawler Python hiện tại để thu thập job IT theo từng cửa sổ thời gian, bắt đầu với nhóm Data. Mỗi website có spider/parser, giới hạn request, trạng thái và quyền bật riêng; các nguồn dùng chung hợp đồng job và cách ghi nhận kết quả.

- **Crawler:** Scrapy; spider riêng cho từng nguồn, dùng Scrapy Request/Response, Selector, Item và Item Pipeline.
- **Lấy trang:** HTTP/HTML hoặc API/feed được nguồn cho phép là lựa chọn đầu tiên. Chỉ cân nhắc `scrapy-playwright` khi đã xác nhận quyền truy cập và nội dung bắt buộc cần JavaScript.
- **Dữ liệu:** PostgreSQL; giữ source identity, URL gốc, mô tả và trạng thái lấy chi tiết theo quyền nguồn.
- **Điều phối:** Airflow/Docker tiếp tục cho môi trường local hiện có. Kế hoạch nền tảng miễn phí dùng GitHub Actions cho các lát nhỏ khi triển khai hosted. Không cho hai scheduler chạy trùng cùng source/window.
- **Không dùng:** Crawlee hoặc crawler runtime thứ hai. Chỉ xem lại lựa chọn framework qua một spec mới và so sánh đo được nếu có lý do cụ thể.

Chỉ thu thập, lưu, phân tích và hiển thị dữ liệu trong phạm vi nguồn cho phép. Không vượt đăng nhập, CAPTCHA, 403, 429 hoặc biện pháp chống tự động hóa. Khi gặp tín hiệu chặn/giới hạn, spider dừng hoặc pause để operator xem xét.

## 2. Hiện trạng đã xác nhận trong repo

- Cấu hình Scrapy nằm tại `scraper/job_crawler/settings.py`; có spider `it_jobs.py` và `it_jobs_detail.py`.
- Crawler hiện ghi bảng raw `jobs` qua `scraper/job_crawler/pipelines.py`; pipeline đang chạy câu lệnh `CREATE TABLE IF NOT EXISTS` khi mở spider.
- Clean schema nằm trong `scraper/job_crawler/migrations/001_transform_schema.sql`; `run_transform.py` kiểm tra migration này trước khi transform.
- Cấu hình hiện tại đặt `CONCURRENT_REQUESTS_PER_DOMAIN=1`, `DOWNLOAD_DELAY=3` và bật AutoThrottle. `ROBOTSTXT_OBEY=False`; cần xử lý rõ cho spider mới trước khi gọi nguồn thật.
- Middleware `CloudscraperMiddleware`/`curl_cffi` đang bật trong cấu hình hiện tại. Không mặc định tái sử dụng nó trong adapter mới; phải kiểm tra hành vi và chỉ giữ nếu phương thức được nguồn cho phép.
- DAG hiện có trong `dags/job_pipeline.py`; hiện chạy thủ công. Crawler là Scrapy, Airflow chỉ điều phối.
- Danh tính nguồn hiện tại của một số dữ liệu cũ chưa được xác minh; không tự đổi nhãn `WebA` thành TopDev.

Các mục trên là trạng thái mã nguồn đã đọc, không khẳng định container hoặc database đang chạy.

## 3. Kiến trúc đích

```text
Airflow local hoặc GitHub Actions hosted (mỗi lượt chọn source + window)
    ↓
Scrapy Spider riêng theo source
    ↓
Scrapy downloader: robots/policy, throttle, retry có giới hạn, pause khi bị chặn
    ↓
Parser/Item Pipeline theo source → hợp đồng job dùng chung
    ↓
PostgreSQL: job thô, source identity, run/window/checkpoint, trạng thái detail
    ↓
Transform/mapping → jobs_clean, skill mappings
    ↓
Flask web hiện có / website nền tảng theo spec 002
```

Tiến độ backfill được lưu bền vững trong database theo source và window. Scrapy `JOBDIR` chỉ dùng khi thư mục job tồn tại qua lần chạy và phiên bản Scrapy không đổi; không xem filesystem runner GitHub Actions là checkpoint bền vững.

## 4. Cấu trúc module Scrapy dự kiến

```text
scraper/job_crawler/
├── sources/
│   ├── base.py                  # Hợp đồng adapter và policy chung
│   ├── registry.py              # Source được duyệt mới được bật
│   ├── topdev/                  # Spider, parser, config riêng
│   ├── topcv/                   # Thêm sau review nguồn
│   └── vietnamworks/            # Thêm sau review nguồn
├── orchestration/               # Chọn window, checkpoint, tổng kết run
├── storage/                     # PostgreSQL writer và quota guard
├── migrations/                  # SQL version hóa, chạy tường minh
├── spiders/                     # Spider legacy trong giai đoạn chuyển đổi
├── items.py                     # Hợp đồng dữ liệu chung
├── pipelines.py                 # Validate/ghi dữ liệu; không khởi tạo DDL
└── settings.py                  # Scrapy defaults an toàn
```

Không tạo thư mục `crawler/` hay image riêng cho Crawlee. Adapter mới ở trong dự án Scrapy hiện có để dùng chung dependency, DB writer, logging và quy tắc throttle.

## 5. Các giai đoạn triển khai

### Giai đoạn 1 — Quyền nguồn và môi trường

- Tạo hồ sơ riêng cho TopDev với URL người dùng cung cấp, điều khoản, robots, phương thức/feed được cho phép, quyền lưu JD/phân tích/hiển thị và ngày review.
- Hiện adapter TopDev mặc định `pending_review`; không phát request thật cho đến khi quyền sử dụng phù hợp được xác nhận.
- Xác minh Docker/PostgreSQL/Airflow chạy được và áp dụng migration theo lệnh tường minh.
- Rà soát `ROBOTSTXT_OBEY=False`, middleware `CloudscraperMiddleware` và các credential trong legacy path trước khi tái sử dụng.

**Đầu ra:** checklist source có trạng thái rõ ràng; fixture synthetic để phát triển parser khi nguồn chưa được duyệt.

### Giai đoạn 2 — Hợp đồng Scrapy và kiểm soát tải

- Tạo Scrapy adapter interface cho discover/list/detail/normalize và chính sách source.
- Cấu hình baseline tối đa 1 request/domain, delay tối thiểu 3 giây, AutoThrottle và kiểm tra robots cho nguồn mới; tăng delay khi nguồn yêu cầu.
- Xử lý 403, 429, login wall, CAPTCHA và tín hiệu chặn thành pause/block có nguyên nhân; retry giới hạn, không đổi IP/giả danh tính để vượt hạn chế.
- Tách parser từng website khỏi Item Pipeline và transform chung.
- Tách DDL sang migration có version; không tạo/sửa schema khi mở spider hoặc mỗi transform.

**Đầu ra:** Scrapy spider fixture chạy qua item contract và policy mà chưa cần request ra nguồn.

### Giai đoạn 3 — TopDev theo window

- Triển khai Scrapy spider danh sách và trang chi tiết TopDev bằng fixture trước.
- Hỗ trợ operator chọn khoảng năm/tháng/ngày; ghi trạng thái và số liệu riêng cho từng window.
- Upsert theo `(source_id, source_job_key)` hoặc khóa URL chuẩn hóa đã xác minh; không gộp tin giữa hai nguồn.
- Giữ mô tả hợp lệ cũ khi lần tải mới lỗi/rỗng; phân biệt listing status với detail status.
- Lưu cursor/checkpoint vào PostgreSQL. Resume sau gián đoạn từ phần chưa hoàn thành.
- Chỉ bật live mode sau khi source permission gate được duyệt.

**Đầu ra:** backfill fixture qua ít nhất ba windows có thể dừng, resume và chạy lại mà không tạo job trùng.

### Giai đoạn 4 — ETL và nguồn dữ liệu phục vụ web

- Dùng migration để tạo schema cần thiết; runtime ingestion không có quyền DDL.
- Nạp job trước rồi mới cập nhật title/skill mappings; transaction và lỗi phải được báo đúng cho orchestrator.
- Không xóa/ghi rỗng description hợp lệ do lỗi fetch; không suy diễn `posted_at` từ thời điểm transform.
- Tách trạng thái raw crawl với dữ liệu clean và thống kê; giữ source label/link để truy nguồn.
- Thống kê phải ghi mẫu số job đã phân tích, nhóm seniority `unknown` và bằng chứng kỹ năng.

**Đầu ra:** dữ liệu fixture được đọc qua web/API hiện có hoặc API contract của feature 002.

### Giai đoạn 5 — Bổ sung adapter theo nguồn

- Review từng ứng viên TopCV, VietnamWorks, Vietlamtot và Xomdata: URL, quyền, robots, định danh job, rate limit, trường dữ liệu và khả năng mô tả.
- Tạo spider/config/parser riêng theo nguồn đã duyệt; dùng chung Scrapy runtime và hợp đồng job.
- Ghi metrics/error/run state theo source; một spider lỗi không dừng spider nguồn khác.
- Thực hiện từng nguồn một; không cam kết connector cho nguồn chưa có phương thức truy cập được phép.

**Đầu ra:** ít nhất hai fixture source chạy độc lập; live source chỉ bật sau review riêng.

### Giai đoạn 6 — Điều phối và vận hành

- Airflow local tiếp tục dùng DAG hiện có trong lúc phát triển. Hosted free run qua GitHub Actions với `workflow_dispatch` và lịch thưa.
- Khóa chạy theo source/window; không chạy đồng thời nhiều spider tới cùng domain.
- GHA xử lý một window nhỏ; checkpoint ở DB vì runner có thể bị kết thúc và lịch schedule không phải queue bền vững.
- Ghi summary theo source/stage: discovered, inserted, updated, detail status, empty/paused/failed, 403/429, parse/DB errors.
- Dừng ingest trước quota free-tier; không bật dịch vụ/overage trả phí.

## 6. Kiểm chứng và tiêu chí hoàn thành

- Parser fixture: map đúng title, company, URL, địa điểm, lương, seniority, ngày và detail status; trường thiếu để null/unknown.
- Resume: ít nhất ba windows, gián đoạn có kiểm soát, resume và chạy lại không trùng khóa tự nhiên.
- Access: source `pending_review` không tạo request mạng; 403/429/login/chặn pause theo policy.
- Data: đối chiếu số raw/clean, không mất source identity, không ghi đè mô tả hợp lệ bằng dữ liệu lỗi.
- Isolation: một fixture source fail không ngăn source fixture khác hoàn thành và báo số liệu riêng.
- Web/analytics: search/detail và skill statistics có sample denominator, unknown seniority và evidence.
- Các bước cần URL/quyền/service thật chỉ được đánh dấu hoàn tất sau khi có evidence; nếu chưa thể truy cập thì ghi chưa xác minh.

## 7. Thứ tự ưu tiên và ước lượng sơ bộ

| Giai đoạn | Phạm vi | Ước lượng ban đầu |
|---|---|---:|
| 1–2 | Quyền nguồn, Scrapy interface, migration và fixture | 2–3 ngày công |
| 3 | Backfill windows và detail cho nguồn được duyệt | 2–4 ngày công |
| 4 | ETL, public read model và kiểm chứng | 2–4 ngày công |
| 5 | Mỗi adapter bổ sung | khảo sát rồi ước lượng riêng |
| 6 | Điều phối hosted, quota và runbook | 1–2 ngày công |

Đây là ước lượng cho lập kế hoạch, chưa phải cam kết; phụ thuộc quyền nguồn, khả năng truy cập và phạm vi dữ liệu.

## Tài liệu Scrapy tham chiếu

- [Scrapy settings: concurrency, delay và robots](https://docs.scrapy.org/en/latest/topics/settings.html)
- [Scrapy AutoThrottle](https://docs.scrapy.org/en/latest/topics/autothrottle.html)
- [Scrapy pause and resume jobs](https://docs.scrapy.org/en/latest/topics/jobs.html)
- [Scrapy downloader middleware](https://docs.scrapy.org/en/latest/topics/downloader-middleware.html)
