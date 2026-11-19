# Implementation Plan: Nền tảng việc làm IT

**Branch**: `002-it-job-platform` (feature directory; current worktree retained) | **Date**: 2026-11-09 | **Spec**: [spec.md](spec.md)

## Summary

Phát triển nền tảng job IT ưu tiên Data theo từng giai đoạn có thể tiếp tục, lưu dữ liệu có truy vết nguồn, hiển thị job và mô tả được phép sử dụng, rồi phân tích kỹ năng theo trình độ với bằng chứng từ mô tả. Giữ Python 3.10 và dùng Scrapy làm framework duy nhất cho crawler hiện tại lẫn mọi adapter nguồn mới; không triển khai Crawlee song song. Dùng GitHub Actions để chạy từng lát backfill có checkpoint bền vững, Supabase Free làm PostgreSQL/API cho MVP, và Cloudflare Pages cho website tĩnh. Thiết kế từng Scrapy spider độc lập, có hạn mức riêng và quyền bật nguồn riêng.

TopDev vẫn là nguồn được người dùng chọn đầu tiên, nhưng trạng thái quyền lưu trữ và hiển thị nội dung chưa được xác nhận. Điều khoản công bố của TopDev hạn chế sao chép, phân phối và hiển thị nội dung; vì vậy adapter TopDev ở trạng thái `pending_review` và không được phát sinh request thu thập cho tới khi xác nhận được nguồn cấp phép/API được phép hoặc chấp thuận bằng văn bản cho phạm vi lưu trữ và hiển thị dự kiến. [Điều khoản TopDev](https://topdev.vn/term-of-services)

## Technical Context

**Language/Version**: Python 3.10 cho crawler/ETL hiện có; HTML, CSS và JavaScript cho website tĩnh.

**Primary Dependencies**: Scrapy là framework duy nhất cho các source spider; PostgreSQL và Supabase Data API cho OLTP/website; DuckDB 2.0 Quack trong Docker Compose cho OLAP cục bộ; GitHub Actions; Cloudflare Pages. Phân tích kỹ năng bản đầu dùng bộ từ điển/alias có phiên bản và bằng chứng trích đoạn; không phụ thuộc API AI trả phí.

**Storage**: Supabase Free PostgreSQL cho MVP, tối đa 500 MB DB mỗi project và 1 GB file storage; không lưu ảnh/logo tải về nếu không cần. Giữ bản dump ngoài dịch vụ theo thao tác của người vận hành. Dừng nhận dữ liệu mới trước ngưỡng 80% quota DB để còn chỗ vận hành; cảnh báo từ 70%. Giới hạn hiện tại phải được kiểm tra lại khi triển khai.

**Data layers**: Dữ liệu job phục vụ website nằm ở PostgreSQL OLTP (`public` và các view/RPC công khai có kiểm soát). Warehouse phân tích nằm trong DuckDB container riêng, schema `warehouse`, file database trên named volume độc lập. Migration được chạy tường minh; không chạy DDL mỗi lần ETL. DuckDB chứa star schema, taxonomy phân tích, kết quả phân tích và mart. Bản OLAP cục bộ hiện chưa thay thế bản backup/Parquet cần thiết khi đưa batch lên môi trường cloud.

**Testing**: Chưa xác nhận có test suite tự động cho repo. Các kịch bản kiểm chứng thủ công và lệnh chạy được ghi trong [quickstart.md](quickstart.md); bước tasks sẽ bổ sung harness tối thiểu ở các tầng chịu ảnh hưởng.

**Target Platform**: Website tĩnh trên Cloudflare Pages; Supabase Free cho dữ liệu/API OLTP đọc công khai; GitHub Actions trên runner Linux cho lịch chạy thưa và chạy thủ công; Docker Compose phục vụ PostgreSQL OLTP, DuckDB OLAP và pipeline cục bộ.

**Project Type**: Nền tảng web công khai kết hợp pipeline crawl/ETL theo nguồn và xử lý phân tích văn bản.

**Performance Goals**: Truy vấn danh sách phân trang, truy vấn chi tiết theo ID và thống kê theo giai đoạn; không đặt SLA, RPS hoặc số người dùng đồng thời khi chưa có yêu cầu quy mô. Crawl tối đa 1 request đồng thời trên mỗi domain, giữ độ trễ tối thiểu hiện có 3 giây giữa request và bật AutoThrottle; thiết kế cấu hình để từng nguồn có thể chậm hơn.

**Constraints**: Ngân sách MVP tuyệt đối $0; không bật overage hay tự chuyển sang dịch vụ trả phí. GHA schedule là best-effort, không phải hàng đợi bền vững; checkpoint phải nằm trong DB. Supabase Free có quota thấp, có thể pause sau 7 ngày ít hoạt động và không có automatic backup. OLAP container chỉ publish Quack trên host loopback, cần token riêng và dùng volume bền vững; volume cục bộ chưa phải backup. Không crawl/giữ/hiển thị dữ liệu nguồn khi chưa xác nhận quyền; tôn trọng robots/điều khoản được xác minh; 403, 429, trang đăng nhập hoặc tín hiệu chặn thì giảm tốc/dừng, không vượt bảo vệ. Mọi thay đổi schema phải đi qua migration tường minh, không chạy DDL ở mỗi lượt transform.

**Scale/Scope**: MVP bắt đầu với job Data và các giai đoạn lịch sử mà nguồn cho phép; backfill do người vận hành chia và chọn từng cửa sổ. TopCV, VietnamWorks, Vietlamtot, Xomdata là ứng viên sau, chưa có URL/phạm vi truy cập được xác minh. Số nguồn, số job và quy mô người dùng cuối cùng chưa được chốt; tăng trưởng dữ liệu phải dừng trước quota miễn phí thay vì hứa lưu toàn bộ lịch sử vô hạn.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Kết quả | Thiết kế đáp ứng |
|---|---|---|
| Source Identity and Traceability | PASS | Mọi job giữ source ID và source key/URL; không gộp chéo nguồn nếu chưa xác minh tương đương. |
| Repeatable ETL | PASS | Upsert theo khóa tự nhiên `(source_id, source_job_key)`; checkpoint theo cửa sổ; phép transform có thể chạy lại. |
| Explicit Run Outcomes | PASS | Tách trạng thái `complete`, `empty`, `paused`, `failed` và lỗi theo pha/source; lỗi bắt buộc không được báo thành công. |
| Preserve Valid Data | PASS | Không thay mô tả hợp lệ bằng nội dung rỗng khi lần tải mới lỗi; lưu trạng thái listing và detail riêng. |
| Protected Access | PASS WITH EXTERNAL GATE | Không bật adapter nguồn ở trạng thái quyền `pending`; giới hạn riêng từng nguồn, dừng ở 403/429/login/chặn; secrets chỉ ở GitHub/Supabase secrets. |
| Isolate source adapters | PASS | Mỗi nguồn có module, cấu hình, trạng thái và kết quả độc lập; một nguồn lỗi không làm mất kết quả nguồn khác. |
| Explicit migrations | PASS | Migration có version được chạy tường minh trước pipeline; không tạo/sửa schema trong `ensure_tables()` mỗi lượt transform. |
| Architecture constraint | PASS | Dùng Scrapy cho crawler hiện tại và mọi adapter mới; không thêm Crawlee runtime. GHA thay vai trò lịch chạy hosted cho lát công việc nhỏ; Airflow/Docker hiện có vẫn là môi trường cục bộ trong giai đoạn chuyển đổi. |

**Gate trước triển khai nguồn**: TopDev hiện được đánh dấu `pending_review`. Trước khi gọi URL nguồn, phải xác nhận quyền thu thập, lưu mô tả, dùng cho phân tích và hiển thị công khai theo từng loại dữ liệu; kiểm tra điều khoản/robots và hành vi URL hiện hành. Nếu chưa đủ căn cứ thì giữ adapter tắt và tiếp tục xây dựng/kiểm chứng bằng fixture hoặc nguồn đã được phép. Đây là điều kiện vận hành của FR-001/FR-005, không phải giả định rằng truy cập công khai đồng nghĩa được phép sao chép nội dung.

**Re-check sau thiết kế**: PASS với điều kiện nguồn nói trên. Không có ngoại lệ hiến pháp cần ghi vào Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-it-job-platform/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── job-catalog.openapi.yaml
└── tasks.md                         # tạo ở lệnh $speckit-tasks
```

### Source Code (repository root)

```text
.github/
└── workflows/
    └── job-ingestion.yml            # lịch thưa + workflow_dispatch, xử lý một lát

scraper/
└── job_crawler/
    ├── sources/
    │   ├── base.py                  # giao diện và chính sách chung của adapter
    │   ├── registry.py              # đăng ký nguồn độc lập, mặc định tắt nếu chưa duyệt
    │   ├── topdev/                  # adapter đầu tiên; chỉ bật sau rights gate
    │   └── <source_name>/           # thêm từng website sau khi đánh giá riêng
    ├── orchestration/               # cửa sổ thời gian, checkpoint, run summary
    ├── analysis/                    # taxonomy, alias, skill extraction + evidence
    ├── migrations/                  # migration version hóa, chạy tường minh
    ├── transform/                   # giữ module hiện có và chuyển DDL ra migration
    └── settings.py                  # throttle theo source/domain

web/
├── public/                          # HTML/CSS/JS tĩnh được Cloudflare Pages deploy
├── app.py                           # Flask legacy/local cho tới khi thay thế hoàn tất
└── ...                              # Dockerfile và tài nguyên hiện có trong giai đoạn chuyển đổi

dags/                                # Airflow cục bộ hiện có; không chạy đồng thời cùng GHA
data/                                # bộ từ điển/alias và dữ liệu cấu hình không bí mật
docker-compose.yml                   # môi trường dev hiện tại
```

**Structure Decision**: Tiếp tục mở rộng `scraper/job_crawler/` theo module nguồn Scrapy và dùng `migrations/` hiện có cho schema. Bản preview cục bộ tận dụng Flask hiện có, đọc `job-postgres` bằng role `job_web_reader` chỉ đọc và chỉ bind host vào loopback. Website triển khai công khai vẫn là frontend tĩnh qua Supabase Data API, với quyền view/RPC chỉ đọc được cấp tối thiểu. Airflow hiện tại giữ vai trò tương thích cục bộ; không chạy hai scheduler cùng lúc cho một source/window.

## Complexity Tracking

Không có vi phạm hiến pháp cần biện minh. Supabase, GitHub Actions và Pages được chọn để đáp ứng mục tiêu $0 ở MVP; giới hạn thấp được chấp nhận và thể hiện thành quota gate, coverage và khả năng dừng/tiếp tục.
