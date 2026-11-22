# Báo Cáo Thực Nghiệm Embedding Title Bằng JobBERT V3

> Đánh giá tác động của tín hiệu cấp bậc (level cues) lên không gian embedding 1.024 chiều của **JobBERT V3** trên 3 nhóm ngôn ngữ: Tiếng Anh (`en`), Việt – Anh (`vi-en`), và Tiếng Việt (`vi`).

## 1. Cấu Hình & Phương Pháp Thực Nghiệm

- **Mô hình**: `TechWolf/JobBERT-v3` (Pretrained checkpoint đóng băng / freeze).
- **Không gian Vector**: `1024` chiều (Projection layer nhánh `anchor`).
- **Metric so sánh**: Cosine Similarity và Cosine Distance ($1 - \cos$) giữa hai vector của cùng một bài tuyển dụng:
  1. **Đầu vào 1 (Full Title)**: Title nguyên văn có chứa tiền tố/hậu tố cấp bậc (`Senior`, `Junior`, `Chuyên viên`, `Chuyên gia`...).
  2. **Đầu vào 2 (Level-stripped Title)**: Title đã bóc tách hoàn toàn tín hiệu level, chỉ giữ chức danh nghề nghiệp cốt lõi.
- **Mục tiêu kiểm định chính**: Trả lời câu hỏi **Title Việt–Anh có bị ảnh hưởng nhiều hơn title tiếng Anh khi có tín hiệu level không?**

## 2. Kết Quả Tổng Hợp Theo Ba Nhóm Ngôn Ngữ

### Bảng so sánh nhóm title CÓ TÍN HIỆU LEVEL (Titles with Level Cues)

| Ngôn ngữ | Số title có Level | Mean Cosine Sim | Std Sim | Mean Drift Distance (1 - Cos) | Min Cosine Sim |
|---|:---:|:---:|:---:|:---:|:---:|
| **Tiếng Anh (`en`)** | 20 | **0.9418** | 0.0555 | **0.0582** | 0.8128 |
| **Việt – Anh kết hợp (`vi-en`)** | 17 | **0.9015** | 0.0675 | **0.0985** | 0.7138 |
| **Tiếng Việt thuần (`vi`)** | 16 | **0.8490** | 0.0860 | **0.1510** | 0.6250 |
| **Tiếng Hàn (`ko`)** | 1 | **1.0000** | 0.0000 | **0.0000** | 1.0000 |

### Bảng so sánh TOÀN BỘ TITLE (All Titles, bao gồm cả Unspecified)

| Ngôn ngữ | Tổng số title | Mean Cosine Sim | Std Sim | Mean Drift Distance (1 - Cos) |
|---|:---:|:---:|:---:|:---:|
| **Tiếng Anh (`en`)** | 41 | **0.9699** | 0.0487 | **0.0301** |
| **Việt – Anh kết hợp (`vi-en`)** | 26 | **0.9295** | 0.0687 | **0.0705** |
| **Tiếng Việt thuần (`vi`)** | 19 | **0.8728** | 0.0962 | **0.1272** |
| **Tiếng Hàn (`ko`)** | 1 | **1.0000** | 0.0000 | **0.0000** |

## 3. Phân Tích Chuyên Sâu: Title Việt–Anh Có Bị Ảnh Hưởng Nhiều Hơn Tiếng Anh?

1. **Mức độ trôi vector (Drift Distance = 1 - Cosine Similarity)**:
   - **Tiếng Anh (`en`)**: Drift trung bình = `0.0582`
   - **Việt – Anh (`vi-en`)**: Drift trung bình = `0.0985`
   - **Tiếng Việt (`vi`)**: Drift trung bình = `0.1510`

> [!IMPORTANT]
> **KẾT LUẬN QUAN TRỌNG**: **Có, title Việt–Anh bị ảnh hưởng nhiều hơn title tiếng Anh** (độ trôi vector cao hơn gấp khoảng **1.69 lần**).
> - Khi một title tiếng Anh thêm từ `Senior` (như `Senior Business Analyst` so với `Business Analyst`), JobBERT V3 đã được pretrained trên hàng triệu cặp title tiếng Anh nên vẫn nhận diện được sự tương đồng nghề nghiệp rất cao (cosine similarity thường > 0.88 - 0.92).
> - Ngược lại, khi các từ level tiếng Việt như `Chuyên viên`, `Chuyên viên cao cấp`, `Chuyên gia` đứng cạnh các từ kỹ thuật tiếng Anh (như `Chuyên viên lập trình Back-end (Java)`, `Chuyên viên Cao cấp QA`), các token tiếng Việt này chiếm tỷ trọng chú ý (attention weight) lớn, làm vector bị kéo lệch khỏi tâm họ nghề tiếng Anh nhiều hơn.

## 4. Các Title Có Độ Trôi Lệch Vector Lớn Nhất (Top Drift Cases)

Dưới đây là các case mà sự xuất hiện của từ ngữ level làm thay đổi vector embedding nhiều nhất (Cosine Similarity thấp nhất):

| ID | Title Gốc (Full) | Title Đã Bóc Level | Ngôn ngữ | Họ nghề | Cosine Sim | Cosine Distance |
|:---:|---|---|:---:|---|:---:|:---:|
| `TITLE-021` | Chuyên viên cao cấp Kiểm thử | Kiểm thử | `vi` | Software Testing / QA / QC | **0.6250** | 0.3750 |
| `TITLE-007` | Chuyên Gia Vận Hành Thẻ | Vận Hành Thẻ | `vi` | IT Operations & Integration Services | **0.7054** | 0.2947 |
| `TITLE-011` | Chuyên viên Cao cấp QA | QA | `vi-en` | Software Testing / QA / QC | **0.7138** | 0.2862 |
| `TITLE-069` | Nhân Viên Hành Chính: Gán Nhãn Dữ Liệu Hình Anh AI - Không Yêu Cầu Kinh Nghiệm | Hành Chính: Gán Nhãn Dữ Liệu Hình Anh AI - Không Yêu Cầu Kinh Nghiệm | `vi-en` | Data Annotation | **0.7650** | 0.2350 |
| `TITLE-023` | Chuyên viên cao cấp Vận hành hệ thống | Vận hành hệ thống | `vi` | Cloud, Systems & Network Infrastructure | **0.7806** | 0.2194 |
| `TITLE-022` | Chuyên viên cao cấp Phát triển Hệ thống | Phát triển Hệ thống | `vi` | Software Engineering (Backend) | **0.8011** | 0.1989 |
| `TITLE-039` | DevOps Engineer (Middle/Senior) | DevOps Engineer | `en` | DevOps & DevSecOps | **0.8128** | 0.1872 |
| `TITLE-024` | Chuyên viên cao cấp an ninh mạng | an ninh mạng | `vi` | Information Security / Cybersecurity | **0.8180** | 0.1820 |
| `TITLE-008` | Chuyên Viên Cao Cấp Vận Hành An Toàn An Ninh Thông Tin - Hà Nội | Vận Hành An Toàn An Ninh Thông Tin | `vi` | Information Security / Cybersecurity | **0.8347** | 0.1653 |
| `TITLE-043` | Expert/Senior/Middle Software Engineer (Java, Spring boot, PostgreSQL) | Software Engineer (Java, Spring boot, PostgreSQL) | `en` | Software Engineering (Backend) | **0.8352** | 0.1648 |
| `TITLE-029` | Chuyên viên triển khai dự án | triển khai dự án | `vi` | IT Support & Systems Operations | **0.8430** | 0.1570 |
| `TITLE-049` | IT Senior Staff | IT Staff | `en` | IT Support & Systems Operations | **0.8511** | 0.1489 |
| `TITLE-014` | Chuyên viên Hỗ trợ bán hàng (Kỹ thuật) | Hỗ trợ bán hàng (Kỹ thuật) | `vi` | IT Sales & Presales | **0.8515** | 0.1485 |
| `TITLE-084` | [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior) | QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | `vi-en` | Database Administration | **0.8765** | 0.1235 |
| `TITLE-083` | [HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA | `vi-en` | Database Administration | **0.8787** | 0.1213 |

## 5. Khuyến Nghị Khi Áp Dụng JobBERT V3 Để Gom Nhóm Chức Danh IT

1. **Bắt buộc tiền xử lý tách tín hiệu Level trước khi Cluster**:
   - Đối với bài toán gom nhóm họ nghề (Role Family Clustering), **phải dùng `level_stripped_title`** làm đầu vào encode cho JobBERT V3 thay vì title nguyên văn.
   - Việc này triệt tiêu độ lệch do `Chuyên viên cao cấp` hay `Senior` gây ra, giúp các chức danh cùng vai trò (dù ở cấp bậc nào) quy tụ về cùng một cụm ngữ nghĩa chuẩn xác.
2. **Tận dụng nhánh `anchor` đúng chuẩn Model Card**:
   - Nhánh `anchor` áp dụng lớp chiếu bất đối xứng (asymmetric linear projection) đưa vector về 1.024 chiều, mang lại biểu diễn ngữ nghĩa tối ưu nhất cho chức danh nghề nghiệp.
3. **Lưu trữ độc lập 2 chiều thông tin**:
   - Chiều 1: Họ nghề suy ra từ embedding JobBERT của `level_stripped_title`.
   - Chiều 2: Level được trích xuất riêng bằng rule/regex/NER (`level_cue`) để giữ nguyên thông tin cấp bậc mà không làm nhiễu họ nghề.