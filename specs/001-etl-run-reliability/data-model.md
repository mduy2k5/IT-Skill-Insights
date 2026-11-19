# Mô hình dữ liệu: Độ tin cậy của lượt ETL

Feature không thay đổi cột job/mapping; migration thêm bảng ledger schema_migrations để ghi phiên bản schema clean đã áp dụng. Các thực thể dưới đây mô tả dữ liệu và trạng thái xử lý.

## Thực thể và quy tắc

| Thực thể | Biểu diễn hiện tại | Quy tắc trong feature |
| --- | --- | --- |
| Lượt ETL | Một lần chạy của job transform; trạng thái lưu trong log và trạng thái task | Phân biệt succeeded, no_data và failed; tóm tắt số lượng theo bước và nguồn; không thêm bảng lịch sử lượt chạy |
| Job nguồn | Một dòng trong jobs, gồm status_crawl_detail | Chỉ đọc nhãn nguồn đang được cấu hình; không đổi tên WebA hoặc thay chính sách ghi raw. Khi detail chưa hoàn tất, trường detail rỗng không ghi đè giá trị clean không rỗng |
| Job chuẩn hóa | Một dòng trong jobs_clean | Link tiếp tục là khóa duy nhất hiện tại. Nếu link cùng nguồn tồn tại và nội dung đổi thì cập nhật dòng đó. Nếu link đã thuộc nguồn khác thì báo xung đột và giữ nguyên dữ liệu cũ |
| Từ điển tham chiếu | Các bảng company, location, level, tag, date, job type, skill và job title cùng các CSV hiện có | Tải thành công trước khi mapping; giữ nguyên danh sách và quy tắc matching hiện hành |
| Mapping kỹ năng | fact_job_skill_mapping | Với job mới hoặc thay đổi, thêm mapping phù hợp và gỡ mapping cũ không còn đúng; khóa kép job/skill tiếp tục chống trùng |
| Mapping cấp bậc | job_level_mapping | Đồng bộ quan hệ cấp bậc của job mới hoặc thay đổi; gỡ quan hệ cũ không còn phù hợp |
| Mapping chức danh | jobs_clean.job_title_mapping_id | Tính lại cho job mới hoặc thay đổi; gỡ giá trị cũ nếu tiêu đề hiện tại không còn khớp từ điển |
| Bản tóm tắt lượt chạy | Kết quả tạm trong log và task state | Gồm nhãn nguồn, số đầu vào, số chuẩn hóa, số job mới/cập nhật/không đổi, số mapping thêm/gỡ bước lỗi và thông tin lỗi đã loại credential/token nếu có |
| Phiên bản migration | Một dòng trong schema_migrations cho mỗi migration đã áp dụng | Lưu mã migration và thời điểm áp dụng; transform chỉ đọc ledger để xác nhận schema clean đã được provision |

## Vòng đời và tính nhất quán

1. Người vận hành áp dụng migration SQL có phiên bản trước khi chạy transform. DDL, seed row và ghi version ledger nằm trong một transaction migration; lỗi không ghi version và không xóa dữ liệu job/mapping hiện có.
2. Transform truy vấn schema_migrations để xác nhận version bắt buộc. Nếu ledger/table/version chưa có, dừng với hướng dẫn áp dụng migration; không chạy DDL.
3. Đọc dữ liệu nguồn và chọn nhãn đang cấu hình.
4. Không có job cho nguồn đó: ghi status=no_data và kết thúc bằng trạng thái Airflow skipped.
5. Với batch có dữ liệu, mở một transaction dùng chung cho các helper ETL. Nạp các từ điển, chuẩn hóa/upsert job, rồi đồng bộ mapping kỹ năng, chức danh và cấp bậc.
6. Commit toàn batch chỉ sau khi các bước bắt buộc thành công.
7. Khi bất kỳ bước bắt buộc nào lỗi, rollback các thay đổi của batch hiện tại, giữ nguyên dữ liệu đã commit từ lượt trước, ghi stage lỗi rồi ném lại exception.
8. Đóng connection trong mọi trường hợp.

## Bất biến

- Mỗi link thuộc nhãn nguồn đang xử lý có tối đa một dòng clean.
- Chạy lại dữ liệu không đổi không tạo thêm job hoặc mapping.
- Mapping của job thay đổi phản ánh nội dung mới; quan hệ cũ không còn phù hợp được loại bỏ.
- Xung đột link giữa các nhãn nguồn không được giải quyết bằng cách ghi đè.
- Lỗi xử lý không được để lại một phần dữ liệu đã commit của batch hiện tại.

## Hệ quả

Các helper hiện đang tự mở connection và commit giữa chừng cần nhận connection của batch và trả thống kê thay vì tự quyết định transaction. Migration chỉ chuyển schema clean hiện có sang provision tường minh và thêm metadata ledger; không đổi cột job/mapping hoặc xóa dữ liệu.
