# Nghiên cứu: Độ tin cậy của lượt ETL

## 1. Ranh giới transaction cho một lô

**Quyết định**: Dùng chung một kết nối psycopg2 cho các bước ghi job chuẩn hóa và mapping trong một lô. Chỉ commit khi toàn bộ bước bắt buộc hoàn tất; khi có lỗi, rollback lô rồi ném lại lỗi. Đóng kết nối rõ ràng trong finally. Schema clean được provision bằng migration tường minh trước lượt ETL; transform chỉ đọc phiên bản migration, không chạy DDL.

**Lý do**: PostgreSQL bảo đảm thay đổi trong một transaction được commit toàn bộ hoặc rollback toàn bộ. Các cursor trên một psycopg2 connection dùng chung một phiên và transaction; các helper mở connection riêng không thể rollback lẫn nhau. Context manager của psycopg2 quản lý commit/rollback nhưng không đóng connection.

**Phương án khác**:

- Giữ nhiều connection và bù trừ từng thao tác: không đảm bảo rollback toàn bộ lô.
- Dùng two-phase commit: quá phức tạp cho một database PostgreSQL.
- Dùng savepoint cho từng dòng: không cần trong phạm vi này vì lỗi ở bước bắt buộc phải rollback toàn lô.

**Nguồn chính thức**: [PostgreSQL 13: Transactions](https://www.postgresql.org/docs/13/tutorial-transactions.html), [psycopg2: Transaction control](https://www.psycopg.org/docs/usage.html#transactions-control), [psycopg2: Connection objects](https://www.psycopg.org/docs/connection.html).

## 2. Trạng thái lỗi và không có dữ liệu trong Airflow

**Quyết định**: Lỗi ở bước bắt buộc phải thoát khỏi entrypoint dưới dạng exception để tiến trình trả mã khác 0. BashOperator đánh dấu task thất bại với mã khác 0; dùng mã 99 cho kết quả không có dữ liệu để Airflow đánh dấu task skipped, đồng thời ghi status=no_data trong log. Giữ trigger rule mặc định all_success.

**Lý do**: Catch lỗi rồi chỉ print sẽ khiến lệnh trả mã 0 và Airflow báo thành công. Mã 99 mặc định của BashOperator biểu thị skipped; trạng thái này phân biệt lô không có dữ liệu với lô đã xử lý và với lỗi. Theo cấu hình hiện tại, exception có thể ở trạng thái up_for_retry trước khi chuyển sang failed sau khi hết retry.

**Giới hạn cần thể hiện đúng**: Failure callback hiện tại chỉ in nội dung, chưa gửi thông báo bên ngoài. Không mô tả nó như một hệ thống alert.

**Phương án khác**:

- Trả mã 0 cho lô rỗng: đơn giản nhưng task bị tính là đã hoàn tất xử lý dữ liệu.
- Dùng all_done: cho phép bước phụ thuộc tiếp tục sau lỗi và trái với yêu cầu dừng sớm.
- Ném AirflowFailException cho mọi lỗi: bỏ qua retry; không phù hợp với các lỗi có thể tạm thời.

**Nguồn chính thức**: [Airflow 2.9: BashOperator](https://airflow.apache.org/docs/apache-airflow/2.9.0/howto/operator/bash.html), [Airflow 2.9: Task states and exceptions](https://airflow.apache.org/docs/apache-airflow/2.9.0/core-concepts/tasks.html), [Airflow 2.9: DAG trigger rules](https://airflow.apache.org/docs/apache-airflow/2.9.0/core-concepts/dags.html), [Airflow 2.9: Callbacks](https://airflow.apache.org/docs/apache-airflow/2.9.0/administration-and-deployment/logging-monitoring/callbacks.html), [Airflow 2.9: Callback context](https://airflow.apache.org/docs/apache-airflow/2.9.0/templates-ref.html).

## 3. Tương thích với dự án hiện tại

**Quyết định**: Giữ Python 3.10, pandas, psycopg2, PostgreSQL, Airflow và cấu trúc chạy hiện có; không thêm thư viện hoặc bảng theo dõi lượt chạy. Thêm file migration SQL có phiên bản và bảng ledger nhỏ để ghi nhận migration schema clean. Tính năng chỉ làm mới bảng clean và mapping cho nguồn đang cấu hình.

**Lý do**: Dockerfile dùng Python 3.10; docker-compose hiện dùng PostgreSQL 13 và Airflow 2.9.0. Mã hiện tại đã có khóa duy nhất theo link ở jobs_clean và các bảng mapping cần thiết. Repo không có suite test hoặc thư mục test được khai báo.

**Giới hạn**: Migration chỉ chuyển các bảng, index, constraint và seed hiện do ensure_tables tạo sang bước provision tường minh; không đổi cấu trúc dữ liệu job/mapping hoặc chính sách cập nhật ở bảng raw. Chi tiết crawler và nguồn ngoài WebA không thuộc feature này. Schema raw do crawler quản lý không nằm trong migration clean. Dữ liệu và trạng thái dịch vụ phải được kiểm tra ở môi trường chạy trước khi xác nhận kết quả thực tế.

**Bằng chứng nội bộ**: [scraper/Dockerfile](../../scraper/Dockerfile), [docker-compose.yml](../../docker-compose.yml), [dags/job_pipeline.py](../../dags/job_pipeline.py), [PIPELINE_REVIEW.md](../../PIPELINE_REVIEW.md), [PROJECT_CHECKLIST.md](../../PROJECT_CHECKLIST.md).

## 4. Provision schema clean bằng migration tường minh

**Quyết định**: Chuyển DDL clean hiện có từ ensure_tables() sang scraper/job_crawler/migrations/001_transform_schema.sql. File tạo schema_migrations, các bảng/index/constraint/seed hiện hành trong một transaction và ghi phiên bản 001_transform_schema sau khi provision thành công. Người vận hành áp dụng file trước khi chạy transform; run_transform chỉ kiểm tra ledger và báo hướng dẫn nếu migration chưa có.

**Lý do**: Repository chưa có migration framework. Một file SQL có phiên bản dùng được bằng PostgreSQL client sẵn có, không thêm dependency runtime, giữ DDL ngoài lượt ETL và hỗ trợ DB mới lẫn DB đã có schema. Các lệnh tạo object dùng điều kiện tồn tại và constraint được kiểm tra trước khi thêm; migration không xóa job hoặc mapping.

**Phương án khác**:

- Giữ ensure_tables() trong transform: tiếp tục chạy DDL mỗi lượt và trái constitution.
- Thêm Alembic hoặc migration framework khác: thêm dependency và khối vận hành mới dù phạm vi chỉ có một migration SQL.
- Chạy DDL trong mỗi lần khởi động Compose: không tạo ranh giới nâng cấp tường minh mà plan yêu cầu.

**Giới hạn**: Migration bảo đảm không xóa dữ liệu hiện có. Nếu database có orphan hoặc schema drift khiến constraint không thể thêm, transaction migration phải thất bại và cần điều tra riêng; migration không tự sửa dữ liệu job.
