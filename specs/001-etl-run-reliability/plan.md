# Implementation Plan: Độ tin cậy của lượt ETL

**Branch**: 001-etl-run-reliability (feature id; Git branch not created) | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Đặc tả tại specs/001-etl-run-reliability/spec.md

## Summary

Làm cho đường transform hiện có có kết quả rõ ràng, cập nhật job chuẩn hóa theo link hiện tại, đồng bộ lại mapping của job mới/thay đổi và rollback toàn batch nếu bước bắt buộc lỗi. Giữ nguyên nhãn WebA và quy tắc matching hiện hành. Chuyển DDL clean hiện có sang một migration SQL có phiên bản, áp dụng tường minh trước ETL; runner chỉ kiểm tra ledger, không tạo/sửa schema. Dùng một psycopg2 connection cho các ghi dữ liệu của batch; để exception thoát khỏi tiến trình để Airflow nhận thất bại.

## Technical Context

**Language/Version**: Python 3.10 trong scraper Docker image.

**Primary Dependencies**: pandas và psycopg2-binary đang dùng; Airflow BashOperator điều phối. Không thêm thư viện.

**Storage**: PostgreSQL 13, hiện có jobs, jobs_clean, dimension tables, job_level_mapping và fact_job_skill_mapping; thêm bảng schema_migrations để ghi nhận migration đã áp dụng.

**Testing**: Repo không có suite test hoặc thư mục test tracked. Kịch bản migration, đối soát dữ liệu và transform được ghi trong quickstart.md; runtime chưa được xác nhận trong phiên lập kế hoạch.

**Target Platform**: Linux containers; Airflow 2.9.0 gọi container scraper qua BashOperator; PostgreSQL 13.

**Project Type**: Data pipeline trong một repository.

**Performance Goals**: Không đặt SLA mới. Giữ batch hiện tại cho nhãn nguồn cấu hình; mapping lại job mới/thay đổi và các job còn chưa có mapping, không dựng lại toàn bộ dữ liệu hoặc thêm full-table rewrite không cần thiết.

**Constraints**: Giữ nhãn nguồn và khóa link hiện hành; không gộp link của hai nhãn nguồn. Dữ liệu clean và mapping của một batch dùng cùng transaction. Schema clean được provision bằng migration tường minh, không qua DDL lúc transform. Không sửa schema dữ liệu job, policy ghi raw, detail crawler, cách matching, API hoặc dashboard.

**Scale/Scope**: Chỉ nhãn WebA đang được transform; số lượng xử lý vẫn theo batch hiện tại. Không thêm TopCV, VietnamWorks hoặc LinkedIn. URL nguồn và tình trạng dịch vụ phải được kiểm chứng riêng.

## Constitution Check

| Nguyên tắc | Cổng | Cách đáp ứng |
| --- | --- | --- |
| Source Identity and Traceability | Pass | Giữ nguyên nhãn WebA và link; link thuộc nhãn khác báo xung đột thay vì ghi đè |
| Repeatable ETL | Pass trong phạm vi clean | Upsert job chuẩn hóa theo link; xử lý lại dữ liệu không tạo bản sao; mapping cũ bị loại khi nội dung thay đổi |
| Explicit Run Outcomes | Pass | Có status succeeded/no_data/failed, summary theo bước và exception được truyền tới tiến trình gọi |
| Preserve Valid Data | Pass trong phạm vi transform | Một connection và transaction bao trùm các ghi của batch; lỗi rollback batch hiện tại, giữ dữ liệu commit trước đó |
| Protected Access | Pass | Không thêm hoặc ghi log credential/session; không thay cách truy cập nguồn |
| Architecture and Data Constraints | Pass | DDL clean chỉ chạy qua migration có phiên bản; transform chỉ đọc ledger. Không thêm framework hoặc thay cấu trúc job/mapping hiện có |

DDL của schema raw do crawler quản lý, detail crawling và các vấn đề khác vẫn nằm ngoài phạm vi feature này; migration mới chỉ bao phủ schema clean hiện do ensure_tables() provision.

## Phương án kỹ thuật

1. Chuyển các bảng, index, constraint và hàng seed clean hiện có sang scraper/job_crawler/migrations/001_transform_schema.sql. Migration tạo schema_migrations, chạy trong một transaction và ghi version 001_transform_schema sau khi thành công; DDL không chạy trong ETL.
2. Trước khi đọc dữ liệu, runner kiểm tra version migration qua truy vấn chỉ đọc. Nếu chưa có, dừng với hướng dẫn áp dụng migration; không tạo hoặc sửa schema.
3. Đọc batch raw và lọc nhãn nguồn đang cấu hình. Nếu đọc thành công nhưng không có job WebA, ghi status=no_data và trả mã 99 để BashOperator đánh dấu skipped.
4. Refactor các helper nạp từ điển/mapping để nhận connection của runner. Không để helper tự mở connection hoặc commit trong transaction batch.
5. Nạp từ điển và các dimension cần thiết, chuẩn hóa batch, rồi upsert jobs_clean theo link. Cập nhật nội dung khi khác; nếu link đã thuộc source khác thì báo lỗi định danh. Khi status_crawl_detail là false, giữ responsibilities, skills, benefits clean không rỗng nếu giá trị raw tương ứng đang rỗng.
6. Với job mới hoặc nội dung đổi, tính lại mapping kỹ năng, chức danh và cấp bậc; gỡ mapping cũ không còn phù hợp. Tiếp tục xử lý job hiện có chưa có skill mapping để bù những job bị bỏ sót do thứ tự cũ.
7. Tập hợp số lượng đã đọc, chuẩn hóa, mới/cập nhật/không đổi, mapping thêm/gỡ và source label; ghi summary khi thành công.
8. Bọc các bước ghi trong một transaction chung. Khi có lỗi, ghi stage và thông tin exception đã loại credential/token, rollback rồi re-raise; đóng connection trong finally.
9. Đặt skip_on_exit_code=99 rõ ràng trên BashOperator để no_data có trạng thái nhất quán với tài liệu.

## Project Structure

### Documentation (this feature)

    specs/001-etl-run-reliability/
      plan.md
      research.md
      data-model.md
      quickstart.md
      tasks.md
      checklists/requirements.md
      migrations/001_transform_schema.sql

### Source Code (existing project)

    scraper/job_crawler/run_transform.py
    scraper/job_crawler/transform/database.py
    scraper/job_crawler/migrations/001_transform_schema.sql
    scraper/job_crawler/job_skill_requirement_transform.py
    scraper/job_crawler/job_title_transform.py
    dags/job_pipeline.py

**Structure Decision**: Keep the feature inside the existing crawler/transform package. A versioned SQL file owns clean-schema provisioning and a schema_migrations ledger records applied versions. The runner performs a read-only migration preflight, then owns stage order, transaction lifetime and run summary. database.py owns data writes; skill/title helper modules accept the shared connection and return mapping statistics. dags/job_pipeline.py only declares the no-data skip code explicitly. No migration framework, public API or test package is introduced.

## Phase 0: Nghiên cứu

Kết quả và nguồn tham khảo ở [research.md](research.md). Các quyết định đã chốt: một transaction/connection cho batch; migration SQL tường minh ngoài ETL; mã khác 0 để báo lỗi; mã 99 cho no_data; giữ stack hiện tại.

## Phase 1: Thiết kế và hợp đồng

### Mô hình dữ liệu

[data-model.md](data-model.md) mô tả ETL run summary tạm thời, dữ liệu raw/clean hiện có, từ điển, vòng đời mapping và ledger phiên bản migration. Schema dữ liệu job/mapping không đổi; chỉ thêm metadata theo dõi migration.

### Hợp đồng

Không tạo contracts/: feature chỉ thay đổi xử lý nội bộ của job transform, không đổi HTTP API hoặc định dạng dữ liệu trao đổi giữa hệ thống.

### Hướng dẫn kiểm chứng

[quickstart.md](quickstart.md) mô tả cách áp dụng migration, lệnh chạy, đối soát SQL, kịch bản job mới/thay đổi, no_data, xung đột link và rollback trong database dùng riêng.

### Cổng constitution sau thiết kế

Pass. DDL clean chạy qua migration có phiên bản trước ETL; transform không chạy DDL. Một transaction bao trùm ghi job/mapping; no_data và failure có trạng thái riêng; nguồn và link được giữ; không thêm credential, thay schema job/mapping hoặc giao diện công khai. Các vấn đề ngoài phạm vi được ghi tại PROJECT_CHECKLIST.md.
