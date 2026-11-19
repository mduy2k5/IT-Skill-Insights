# Quickstart: Nền tảng việc làm IT

Hướng dẫn này định nghĩa đường kiểm chứng sau khi các task của feature được triển khai. Không cần bật crawl nguồn thật để kiểm tra trạng thái/quy trình: dùng adapter fixture cho các trường hợp thông thường và đảm bảo TopDev đang `pending_review` cho tới khi có quyền sử dụng đã được xác minh.

## Prerequisites

- Python 3.10 và Docker Compose cho môi trường phát triển cục bộ.
- Một Supabase Free project do người vận hành tạo; ghi nhận quota trước khi nạp dữ liệu. Tạo role DB riêng cho ingestion với quyền tối thiểu, và chỉ chạy migration qua operator/CLI.
- Secrets `SUPABASE_DB_URL` (role ingestion), `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (website đọc công khai), cùng `CLOUDFLARE_ACCOUNT_ID`/token deploy nếu bật deployment. Không dùng publishable key để ghi dữ liệu và không đặt DB URL/secret key vào frontend.
- GitHub Actions workflow bật trên repository sau khi xác nhận visibility, quyền repo và mức usage. Cấu hình chặn overage để usage vượt allowance bị dừng thay vì bị tính phí.
- Một fixture JSON/HTML được tạo cục bộ, không chứa nội dung lấy từ nguồn khi chưa được phép.

## Bring up the local base

```powershell
docker compose up --build
```

Kết quả mong đợi: PostgreSQL, Scrapy, Airflow và Flask hiện có khởi động được theo cấu hình repo. Đây là môi trường dev của base hiện tại; không chạy cùng lúc DAG Airflow và workflow GitHub Actions cho cùng source/window.

## Xem job đã nạp trên Flask cục bộ

Flask đọc PostgreSQL `job-postgres` bằng role chỉ đọc `job_web_reader`; cổng host chỉ bind vào loopback.

```powershell
docker compose exec -T job-postgres sh /docker-entrypoint-initdb.d/003_web_reader.sh
docker compose up --build -d web
```

Mở `http://localhost:5000`. Trang hỗ trợ tìm theo chức danh/công ty, lọc theo địa điểm, cấp độ và hình thức làm việc, phân trang, rồi mở chi tiết job và toàn bộ `overview_text`. Đây là preview nội bộ; quyền hiển thị công khai của nguồn vẫn được quản lý riêng.

## Apply schema migrations

Sau khi bước tasks bổ sung CLI migration:

```powershell
python -m scraper.job_crawler.cli migrate --database-url $env:SUPABASE_DB_URL
```

Kết quả mong đợi: từng migration chưa áp dụng được ghi version một lần; chạy lại không chạy DDL lặp trong transform. Khi chưa có credential hợp lệ thì dùng PostgreSQL Compose cục bộ và cùng file migration.

## Nạp artifact JSON đã lưu vào PostgreSQL

Artifact phải được nhập trước vào `crawl_artifacts`; loader không gửi request tới website. `--dry-run` chỉ kiểm tra và báo cáo, không ghi dữ liệu:

```powershell
docker compose run --rm scrapy python /app/scraper/job_crawler/load_crawl_artifacts.py --source-code saramin --artifact-filename embedded_jobs_compact_company_2026-11-09.json --project-track data --dry-run
```

Sau khi xem báo cáo, chạy `--verify` để lưu từng record JSON vào `job_ingest_candidates`. Lỗi sẽ được lưu với trạng thái `rejected`; record có cảnh báo sẽ ở `needs_review`; record không có lỗi/cảnh báo sẽ ở `verified`. Tất cả đều giữ JSON và lỗi/cảnh báo để xem lại, nhưng bước này không ghi các bảng job của website:

```powershell
docker compose run --rm scrapy python /app/scraper/job_crawler/load_crawl_artifacts.py --source-code saramin --artifact-filename embedded_jobs_compact_company_2026-11-09.json --project-track data --verify
```

Verify kiểm tra ID trùng, tiêu đề/URL bắt buộc, URL HTTP(S), ngày, lương, mô tả, công ty, địa điểm, hình thức làm việc và trạng thái. Đây là kiểm tra cấu trúc/chất lượng tự động; `needs_review` cần được xem xét trước khi xác nhận dữ liệu thực. Chỉ candidate `verified` mới được nạp bằng lệnh có `--apply`:

```powershell
docker compose run --rm scrapy python /app/scraper/job_crawler/load_crawl_artifacts.py --source-code saramin --artifact-filename embedded_jobs_compact_company_2026-11-09.json --project-track data --apply
```

Loader xác nhận đủ candidate đã được staging từ đúng artifact, track và phiên bản validator. Candidate `needs_review`/`rejected` được giữ lại và không nạp. Upsert các candidate `verified` theo khóa `(source_id, source_job_key)` cùng cập nhật trạng thái staging trong một transaction. Nguồn phải có `permission_status=approved` và `allow_store_metadata=true`; mô tả chỉ được ghi khi `allow_store_description=true`. Các đoạn mô tả text sẵn có được nối vào một `overview_text`. Bảng staging không được cấp quyền đọc cho role website.

## Khởi tạo OLAP DuckDB cục bộ

Tạo `JOB_OLAP_TOKEN` riêng trong `.env` trước khi khởi động container. Chạy migration một lần rồi bật server:

```powershell
docker compose --profile olap-tools run --rm --no-deps job-olap-migrate
docker compose up -d job-olap
```

DuckDB lưu file trong volume `it_job_olap_data`; port Quack chỉ bind vào `127.0.0.1:9494`. Migration tạo star schema trong `warehouse`, được theo dõi ở `olap_meta.schema_migrations`. Với migration mới, dừng `job-olap`, chạy migration tương ứng, rồi khởi động lại. OLAP hiện chỉ có schema rỗng; ETL từ job OLTP là bước riêng.

## Validate a source with a local fixture

Sau khi bước tasks bổ sung CLI/fixture adapter:

```powershell
python -m scraper.job_crawler.cli run --source fixture --from 2026-01-01 --to 2026-01-31 --fixture .\data\fixtures\jobs.json
```

Kết quả mong đợi: run ghi source, cửa sổ, số listing, số job inserted/updated và trạng thái kết thúc. Chạy lại cùng fixture không tạo thêm job có cùng `(source_id, source_job_key)`.

Kiểm tra tiếp tục: làm fixture có ít nhất ba cửa sổ; cố ý dừng sau cửa sổ đầu; chạy resume; cửa sổ hoàn thành không bị nhân đôi và các cửa sổ còn lại kết thúc với số liệu riêng.

## Validate access and quota gates without contacting a job site

1. Để `topdev.permission_status=pending_review`, dispatch một run TopDev ở chế độ dry-run.
2. Kết quả phải là `paused` hoặc `skipped` với lý do quyền chưa được xác nhận, `requests_made=0`, không có request tới TopDev.
3. Mock phản hồi 429/403 trong fixture middleware. Run phải giảm tốc hoặc `paused`, ghi error stage/code, không retry vô hạn và không làm trạng thái nguồn fixture khác bị ảnh hưởng.
4. Đặt dung lượng test ở ngưỡng dừng 80% quota. Ingest mới phải dừng trước write, không gửi sang dịch vụ trả phí; coverage và nguyên nhân dừng vẫn được lưu nếu DB còn thao tác được.

## Validate the public website and API

Sau khi build/deploy frontend:

```powershell
python -m http.server 8000 --directory .\web\public
```

Mở `http://localhost:8000`; dùng publishable key và dữ liệu fixture đã được đánh dấu cho phép public. So khớp request/response với [job-catalog.openapi.yaml](contracts/job-catalog.openapi.yaml): tìm kiếm, lọc theo Data/địa điểm/trình độ/khoảng ngày, phân trang, mở chi tiết, thống kê kỹ năng và coverage. Anonymous read không được insert/update/delete, không đọc bảng staging/raw, và description không được hiển thị nếu source thiếu `display_description` permission.

## Validate independent adapters

- Chạy một fixture adapter bình thường và một fixture adapter trả lỗi parse trong cùng phiên kiểm chứng.
- Kết quả nguồn bình thường phải giữ nguyên; nguồn lỗi có status/error riêng. Sau đó chạy lại adapter lỗi với fixture hợp lệ và xác nhận resume.
- Không bật TopCV, VietnamWorks, Vietlamtot hoặc Xomdata cho tới khi có URL, chính sách truy cập, quyền dữ liệu và cấu hình throttling được review riêng.

## Expected observable evidence

- Danh sách `crawl_windows`/`crawl_runs` phân biệt `complete`, `empty`, `paused`, `failed` và có bộ đếm theo nguồn/cửa sổ.
- Mỗi job trong fixture có source identity và URL gốc; rerun giữ số bản ghi duy nhất.
- Mỗi skill trong thống kê fixture có số job phân tích và ít nhất một `job_skill_evidence` có thể truy nguồn.
- Frontend chỉ gọi public views/RPC và không chứa `SUPABASE_DB_URL`, secret key, session cookie hoặc credential crawler.
