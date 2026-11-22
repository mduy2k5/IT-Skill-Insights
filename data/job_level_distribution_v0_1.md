# Phân bố level job — benchmark v0.1

## Phạm vi

- Nguồn: 14 job Saramin trong `skill_benchmark_v0_1.json`.
- Dùng `job_levels_arr` / `source_level` làm nhãn nghề nghiệp. Loại trường raw `level` (`paid` / `free`) khỏi phân tích vì đó là nhãn gói đăng tin, không phải cấp bậc nghề nghiệp.
- `experience_label` được thống kê riêng và giữ nguyên đúng giá trị nguồn; các giá trị nhiều năm được liệt kê như lựa chọn của nguồn, không diễn giải thành khoảng năm kinh nghiệm.

## Nhãn level nguồn

Số job theo nhãn là membership count. Một tin có thể mang nhiều level, nên các hàng không cộng thành số job duy nhất.

| Nhãn nguồn | Job có nhãn | Chỉ có nhãn này | Ánh xạ đề xuất, chưa xác nhận |
|---|---:|---:|---|
| Chuyên viên | 8 | 5 | Junior |
| Nhân viên | 4 | 3 | Fresher |
| Chuyên viên cấp cao | 4 | 2 | Senior |
| Thực tập | 1 | 1 | Intern |

Các giá trị ở cột cuối là giả thuyết cần kiểm tra, không phải kết luận của báo cáo.

- Tổng: 14 job duy nhất, 17 lượt gắn nhãn level.
- 3 job ghi nhiều level: `Chuyên viên cấp cao, Chuyên viên` (2 job); `Nhân viên, Chuyên viên` (1 job).
- Không có nhãn nguồn `Fresher` hoặc `Junior` rõ ràng.

## Tín hiệu cấp bậc trong tên job

Đếm riêng các từ khóa cấp bậc viết rõ trong title; đây là tín hiệu để rà soát, không phải nhãn chuẩn hóa.

| Tín hiệu title | Job |
|---|---:|
| Senior (`Senior`, `Sr.`, `Principal` hoặc `cấp cao`) | 3 |
| Intern (`Intern`, `Internship`, `Trainee` hoặc `thực tập`) | 1 |
| Fresher | 0 |
| Junior | 0 |
| Mid-level | 0 |

- Trong 3 job có tín hiệu Senior ở title, 2 job cũng mang nhãn nguồn `Chuyên viên cấp cao`; 1 job không có nhãn nguồn này: `2144784 — Data Engineer/ Senior Data Engineer` (`Nhân viên, Chuyên viên`). Dấu `/` có thể cho biết tin tuyển nhiều lựa chọn cấp độ, nên chưa thể kết luận đây là Senior duy nhất.
- Chiều ngược lại, 2 job mang nhãn nguồn `Chuyên viên cấp cao` nhưng title không ghi rõ tín hiệu Senior: `2139159 — Tester` và `2141955 — Remote Data Engineer - AI Data Platform Japan (Python)`.
- Vì title có thể lược bỏ level hoặc liệt kê nhiều lựa chọn, không nên dùng riêng title hay nhãn nguồn để ghi đè tín hiệu còn lại.

## Kinh nghiệm yêu cầu

| Giá trị nguồn | Job |
|---|---:|
| 2 năm | 3 |
| 1 năm | 2 |
| 1 năm, 3 năm | 2 |
| Không yêu cầu | 2 |
| 1 năm, 2 năm | 1 |
| 2 năm, 4 năm | 1 |
| 3 năm | 1 |
| 3 năm, 5 năm | 1 |
| 4 năm | 1 |

`Không yêu cầu` xuất hiện ở 2 job: một nhãn `Thực tập`, một nhãn `Chuyên viên`. Vì vậy không dùng riêng điều kiện này để gán nhãn Fresher.

## Giả thuyết ánh xạ cần kiểm chứng

Các ánh xạ dưới đây là giả thuyết do người dùng đề xuất; chưa được xác nhận là quy tắc của nguồn:

| Nhãn nguồn | ID trong snapshot | Giả thuyết cần kiểm tra | Lượt job |
|---|---:|---|---:|
| Thực tập | 1616 | Intern | 1 |
| Nhân viên | 1617 | Fresher | 4 |
| Chuyên viên | 12506 | Junior | 8 |
| Chuyên viên cấp cao | 8665 | Senior | 4 |

Mô tả gốc cho thấy cần kiểm tra từng tin trước khi chấp nhận ánh xạ:

- Nhãn `Nhân viên` có job chấp nhận fresh graduate (`2142369`), nhưng cũng có job ghi 2–4 năm (`2144836`), 1+ năm (`2143923`) và title gồm cả Data Engineer/Senior Data Engineer (`2144784`). Tín hiệu hiện có chưa ủng hộ quy tắc một-một `Nhân viên = Fresher` cho mọi tin.
- Nhãn `Chuyên viên` trải từ `Không yêu cầu` đến 3 năm kinh nghiệm; đa số title không ghi `Junior`. Đây chưa đủ để xác nhận `Chuyên viên = Junior`.
- Trong 4 lượt `Chuyên viên cấp cao`, 2 title ghi Senior; 2 title còn lại là `Tester` và `Remote Data Engineer...` không ghi Senior rõ ràng. Cần đọc yêu cầu và phạm vi trách nhiệm để phân biệt cách đặt nhãn nguồn với cấp nghề nghiệp thực tế.
- `Thực tập` có 1 job, đồng thời title ghi Intern và kinh nghiệm là `Không yêu cầu`; đây là trường hợp nhất quán nhưng mẫu một job chưa xác nhận độ chính xác chung.

Tài liệu Saramin hướng dẫn khai báo `직급/직책` như một mục riêng và tùy chọn khi đăng tin; API Saramin cũng mô tả `experience-level` theo nhóm `신입` (mới), `경력` (đã có kinh nghiệm), `신입/경력`, `경력무관` (không giới hạn). Điều này cho thấy chức danh/cấp bậc và điều kiện kinh nghiệm là các chiều riêng trong mô hình đăng tin của nguồn. Tài liệu hiện có chưa xác nhận trực tiếp `job_levels_arr` tương đương hoàn toàn với một trong các nhóm nghề nghiệp Intern/Fresher/Junior/Senior.

- [Hướng dẫn đăng tin Saramin](https://www.saramin.co.kr/zf_user/help/help-word/main?memberCode=com)
- [Saramin Job Search API: experience-level](https://oapi.saramin.co.kr/guide/job-search)

## Bước rà soát cho Analyst v0.1

1. Giữ nguyên nhãn và ID gốc; ánh xạ không ghi đè dữ liệu nguồn.
2. Rà đủ 17 lượt nhãn trên 14 job. Đánh giá từng cặp job–nhãn nguồn là `Phù hợp`, `Mâu thuẫn` hoặc `Chưa đủ bằng chứng` dựa trên title, kinh nghiệm, yêu cầu và trách nhiệm.
3. Với job có nhiều nhãn nguồn, đánh giá từng nhãn độc lập; ghi chú khi tin tuyển nhiều cấp độ.
4. Lưu kết quả rà cùng bằng chứng và ghi chú; chỉ tổng hợp mức phù hợp theo từng ánh xạ sau khi các trường hợp đã được xử lý. Giữ riêng số trường hợp chưa đủ bằng chứng.
5. Xem 14 job này là đợt kiểm tra ban đầu. Cần kiểm tra thêm job ngoài mẫu trước khi dùng ánh xạ như quy tắc phân loại chung.

Trang Analyst có hàng đợi rà soát, hiển thị mô tả gốc, lưu lựa chọn trong trình duyệt và cho phép tải JSON kết quả. Mọi lượt ban đầu mang trạng thái `Chưa rà`.

## Hai insight chính trên Analyst

Trang Analyst hiện lấy phạm vi job, nhãn level và skill tag trực tiếp từ OLAP. Skill theo level trên trang được tính từ tag nguồn `skills_arr` / `extra_skills`, không lấy từ gold GLiNER. Bảng dưới đây là ảnh chụp benchmark offline v0.1 để đối chiếu giả thuyết level; nó không phản ánh số liệu skill live trên trang Analyst.

Trong Analyst, nhóm job được suy ra từ title; người xem có thể mở từng nhóm để xem các job cụ thể.

| Nhóm job theo title | Job |
|---|---:|
| Data Engineering | 6 |
| Dịch vụ & tích hợp dữ liệu | 3 |
| Quản trị cơ sở dữ liệu | 2 |
| Kiểm thử phần mềm / QA | 1 |
| Cloud, Data Center & mạng | 1 |
| Nghiên cứu định lượng AI | 1 |

Skill theo level trong snapshot benchmark v0.1 được tính từ tập gold (`found + missed`): một skill chỉ tính tối đa một lần trên một job; job đa level xuất hiện trong từng nhóm nhãn nguồn của nó. Chỉ dùng bảng này để mô tả benchmark đóng băng.

| Nhãn nguồn | Job | Skill thường gặp trong nhóm, theo số job |
|---|---:|---|
| Chuyên viên | 8 | MySQL (6), Oracle (5), PostgreSQL (5), SQL (4) |
| Chuyên viên cấp cao | 4 | MySQL (3), PostgreSQL (3), Python (3), SQL (3) |
| Nhân viên | 4 | ETL (4), dbt (3), ELT (3), MySQL (3) |
| Thực tập | 1 | Mỗi skill trong nhóm hiện xuất hiện ở 1 job |

Tần suất mô tả số job có skill trong nhãn gold; đây không phải số lần model trích xuất. Benchmark gán nhãn hiện vẫn là bản nháp một người gán nhãn.

## Chất lượng dữ liệu

OLTP hiện có 17 dòng `seniority` từ `job_levels_arr` trên 14 job và 14 dòng `paid/free` do các lần nạp trước gán trường raw `level` vào `seniority`. Loader mới lưu raw `level` dưới `listing_tier`; các truy vấn level của website cũng lọc riêng `source_field='job_levels_arr'`, nên không trộn `paid/free` vào cấp bậc nghề nghiệp. Dữ liệu OLTP cũ vẫn giữ nhãn trước đó cho tới lần nạp lại artifact.
