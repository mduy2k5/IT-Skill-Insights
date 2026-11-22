# Phương pháp gom nhóm job theo title — v0.1

## Mục tiêu

Chuẩn hóa title để tổng hợp kỹ năng của các job cùng họ nghề, nhưng không sửa title nguồn và không ép title mới vào một nhóm chưa chắc đúng. Level nghề nghiệp vẫn là chiều riêng; từ `Senior`, `Intern`, `Chuyên viên`... trong title không được dùng để đổi nhãn level nguồn.

## Quy trình hiện tại

1. Giữ nguyên title gốc trong `dim_job.title`.
2. Tạo bản dùng để dò: chuẩn hóa Unicode, chữ hoa/thường, dấu tiếng Việt, dấu câu và khoảng trắng. Bản này chỉ phục vụ so khớp, không thay title gốc.
3. Áp dụng các cụm từ đã rà trong [`web/config/job_role_families_v0_1.json`](../web/config/job_role_families_v0_1.json). Quy tắc có version `job-role-family-v0.1`.
4. Chỉ tự gán họ nghề khi title khớp đúng một họ. Không khớp hoặc khớp nhiều họ được đưa vào `Cần rà title`; skill của chúng không được cộng chung vào một hồ sơ nghề tạm.
5. Hiển thị title gốc, source level và nhóm suy ra để rà lại. Mỗi lần thay quy tắc cần tăng version và kiểm tra lại toàn bộ title đã có.

## Kết quả pilot trên 14 job

| Họ nghề tạm | Số job |
|---|---:|
| Data Engineering | 6 |
| Data Services & Integration | 3 |
| Database Administration | 2 |
| Software Testing / QA | 1 |
| Cloud, Data Center & Network | 1 |
| AI Quantitative Research | 1 |
| Cần rà title | 0 |

Đây là nhóm tạm do title và từ khóa quyết định, không phải taxonomy nghề đã được xác nhận. Đặc biệt, cần rà xem `Chuyên viên Hỗ trợ Tích hợp Dịch vụ` có cùng họ với `Data Services Specialist` và `Senior Data Services Consultant` hay cần tách.

## Khi số lượng title tăng

- Giữ rule/alias đã được người rà duyệt làm đường xử lý có độ tin cậy cao.
- Với title mới, dùng tìm kiếm embedding đa ngôn ngữ để đưa ra một vài nhóm ứng viên từ các họ nghề đã duyệt; không tự coi độ tương đồng là nhãn đúng.
- Khi title chứa nhiều nghề hoặc kết quả gần nhau, dùng mô tả công việc làm ngữ cảnh và đưa trường hợp đó vào hàng đợi rà.
- Đo độ chính xác và tỷ lệ phân nhóm được trên tập giữ lại theo thời gian hoặc theo job; đồng thời theo dõi số title phải rà. Chỉ tăng tự động hóa sau khi các ngưỡng được đo trên dữ liệu đại diện.
- Khi quy tắc ổn định, lưu `role_family_id`, trạng thái duyệt và version áp dụng trong OLAP để có thể truy vết kết quả theo lần crawl. Hiện tại Analyst suy ra nhóm lúc đọc từ OLAP và trả về version đang dùng; chưa ghi nhóm chuẩn hóa vào warehouse.

ESCO có occupation concepts, nhãn thay thế, mô tả và quan hệ phân cấp nên có thể cung cấp candidate/reference IDs; tuy nhiên hiện danh sách ngôn ngữ ESCO không bao gồm tiếng Việt. Không dùng taxonomy ngoài làm nhãn bắt buộc nếu mô tả nghề không khớp với cách tuyển dụng thực tế của nguồn.

## Tài liệu tham khảo

- [ESCO occupations and their hierarchy](https://esco.ec.europa.eu/en/classification/occupation-main)
- [ESCO language coverage and access methods](https://esco.ec.europa.eu/en/use-esco)
- [JAMES: Normalizing Job Titles with Multi-Aspect Graph Embeddings and Reasoning](https://arxiv.org/abs/2202.10739)
