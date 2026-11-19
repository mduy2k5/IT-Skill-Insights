# Hướng dẫn kiểm chứng: Độ tin cậy của lượt ETL

## Điều kiện

- Docker Engine hoạt động.
- Các container trong docker-compose khởi động được.
- Hai từ điển data/job_skills.csv và data/job_titles.csv có trong thư mục dữ liệu được mount vào crawler.
- Migration schema clean tại scraper/job_crawler/migrations/001_transform_schema.sql đã được áp dụng cho database mục tiêu.
- Chạy các tình huống ghi hoặc gây lỗi trong một môi trường phát triển dùng database riêng.

## Áp dụng migration schema clean

Khởi động PostgreSQL trước. Với database hiện có, ghi lại số job clean và mapping trước khi áp dụng để đối chiếu sau migration. Từ PowerShell tại thư mục gốc dự án, gửi file migration một lần vào psql:

    docker compose up -d postgres
    $schemaMigration = Get-Content -Raw -LiteralPath 'scraper/job_crawler/migrations/001_transform_schema.sql'
    $schemaMigration | docker compose exec -T postgres psql -U airflow -d airflow -v ON_ERROR_STOP=1

Xác nhận migration có trong ledger:

    docker compose exec -T postgres psql -U airflow -d airflow -c "SELECT version, applied_at FROM schema_migrations ORDER BY version;"

Migration không xóa job hoặc mapping. Nếu lệnh thất bại, transaction migration bị rollback; không chạy transform cho đến khi nguyên nhân được xử lý. Schema clean phải được provision trước khi chạy transform, không được tạo tự động trong lượt ETL.

## Chạy transform

Từ thư mục gốc dự án:

    docker compose up --build -d
    # Chỉ chạy sau khi đã áp dụng migration schema clean ở trên
    docker compose exec scrapy python scraper/job_crawler/run_transform.py

Kết quả có dữ liệu phải kết thúc với status=succeeded và tóm tắt số lượng theo nhãn nguồn cùng từng bước. Transform chỉ truy vấn schema_migrations; nếu thiếu version 001_transform_schema, tiến trình phải dừng với hướng dẫn migration và không thực thi DDL. Nếu truy vấn raw thành công nhưng không có job WebA, log phải ghi status=no_data và tiến trình trả mã 99; BashOperator được cấu hình chuyển mã 99 thành skipped. Lỗi ở bước bắt buộc phải trả mã khác 0, kèm stage và thông tin lỗi đã loại credential/token.

## Đối soát số liệu

Chạy các truy vấn chỉ đọc trong một terminal:

    docker compose exec -T postgres psql -U airflow -d airflow -c "SELECT source, COUNT(*) AS clean_jobs FROM jobs_clean GROUP BY source ORDER BY source;"
    docker compose exec -T postgres psql -U airflow -d airflow -c "SELECT j.source, COUNT(*) AS jobs, COUNT(DISTINCT j.link) AS unique_links, COUNT(DISTINCT f.job_id) AS jobs_with_skill_mapping FROM jobs_clean j LEFT JOIN fact_job_skill_mapping f ON f.job_id = j.id GROUP BY j.source ORDER BY j.source;"
    docker compose exec -T postgres psql -U airflow -d airflow -c "SELECT j.source, COUNT(*) AS jobs, COUNT(DISTINCT l.job_id) AS jobs_with_level_mapping FROM jobs_clean j LEFT JOIN job_level_mapping l ON l.job_id = j.id GROUP BY j.source ORDER BY j.source;"

Đối chiếu nguồn WebA với số raw đã đọc và tóm tắt lượt chạy. COUNT(DISTINCT link) phải bằng số dòng clean trong phạm vi link hợp lệ.

## Kịch bản job mới và job đã đổi

Trong database phát triển riêng:

1. Ghi một job nguồn WebA mới với link duy nhất, cùng tiêu đề/kỹ năng/cấp bậc có trong từ điển.
2. Chạy transform và xác nhận có một dòng clean cùng mapping tương ứng.
3. Chạy lại mà không đổi nội dung; xác nhận số dòng clean và mapping không tăng.
4. Thay skills, tiêu đề hoặc cấp bậc của cùng link trong jobs; chạy lại transform.
5. Xác nhận dòng clean được cập nhật tại chỗ, mapping mới xuất hiện và mapping cũ không còn phù hợp bị gỡ.
6. Gán cùng link cho một nhãn nguồn khác trong fixture riêng; transform phải báo xung đột và không ghi đè dữ liệu của nguồn kia.

## Kịch bản giữ detail khi lần tải chưa hoàn tất

Chỉ thực hiện trong database phát triển dùng riêng:

1. Chọn job đã có responsibilities, skills hoặc benefits không rỗng trong jobs_clean.
2. Trong jobs, đặt các trường detail tương ứng thành rỗng và status_crawl_detail = FALSE cho cùng link.
3. Chạy transform; nếu các trường clean khác không đổi, nội dung detail và mapping kỹ năng hiện có phải được giữ nguyên.
4. Đặt status_crawl_detail = TRUE chỉ trong fixture kiểm chứng riêng nếu cần xác nhận một detail hoàn tất có thể thay nội dung cũ.

## Kịch bản rollback

Thực hiện trên bản sao dự án và database dùng riêng. Gây lỗi đọc một từ điển bắt buộc sau khi một bước ghi của batch đã chạy, rồi chạy transform:

- Tiến trình phải trả mã khác 0 và kết quả phải nêu bước lỗi.
- Airflow có thể hiển thị up_for_retry trong thời gian áp dụng retry; sau khi hết retry, task phải ở trạng thái failed.
- Dữ liệu của batch hiện tại phải rollback toàn bộ; dữ liệu đã commit trước đó phải còn nguyên.
- Các bước mapping phía sau lỗi không được chạy.

Khôi phục bản sao sau tình huống gây lỗi. Không dùng truy vấn gây lỗi hoặc thay từ điển trên database chia sẻ.

## Kiểm tra giới hạn môi trường

Nếu Docker, PostgreSQL, Airflow hoặc các file từ điển không khả dụng, đánh dấu kiểm chứng runtime là chưa thực hiện và ghi rõ thành phần bị thiếu. Báo cáo lịch sử từ logs không thay thế được đối soát database hiện tại.
