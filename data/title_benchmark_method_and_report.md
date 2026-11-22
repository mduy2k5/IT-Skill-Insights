# Benchmark Chuẩn Hóa & Gom Nhóm Title Việc Làm IT (v0.1)

> Mục đích: Xây dựng tập dữ liệu benchmark chuẩn (Ground Truth) phục vụ tinh chỉnh (fine-tune) và đánh giá mô hình **JobBERT V3** trong bài toán gom nhóm họ nghề (Role Family Clustering) và chuẩn hóa chức danh tuyển dụng IT.

## 1. Nguyên Tắc Thiết Kế Benchmark

1. **Tách biệt tuyệt đối giữa Họ nghề (Role Family) và Cấp bậc (Level Cues)**:
   - Các từ khóa như `Senior`, `Junior`, `Intern`, `Fresher`, `Chuyên viên`, `Chuyên viên cao cấp`, `Chuyên gia`, `Lead`, `Manager`... **không bao giờ được xem là họ nghề**.
   - Ví dụ: `Senior Data Engineer` và `Data Engineer (Big Data)` cùng thuộc họ nghề `Data Engineering`, với tín hiệu level lần lượt là `Senior` và `Unspecified`.
2. **Phân nhóm ngôn ngữ 3 loại**:
   - **Tiếng Việt (`vi`)**: Title sử dụng hoàn toàn tiếng Việt (ví dụ: *Chuyên viên Phân tích nghiệp vụ*, *Chuyên viên cao cấp an ninh mạng*).
   - **Việt – Anh kết hợp (`vi-en`)**: Title sử dụng cả tiếng Việt lẫn từ ngữ kỹ thuật/chức danh tiếng Anh (ví dụ: *Kỹ Sư Dữ Liệu (Data Engineer)*, *Chuyên viên lập trình Back-end (Java)*, *[HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior)*).
   - **Tiếng Anh (`en`)**: Title viết bằng tiếng Anh hoàn toàn (ví dụ: *AI Engineer*, *Cloud & DevOps Engineer*, *DevOps Engineer (Middle/Senior)*).
   - *(Trường hợp đặc biệt: `ko` cho các title tiếng Hàn trong doanh nghiệp FDI Hàn Quốc)*.
3. **Tách tín hiệu công nghệ & làm sạch tiền tố/hậu tố nhiễu**:
   - `cleaned_title` loại bỏ địa điểm trong ngoặc (`[HN]`, `[Vũng Tàu]`), trạng thái khẩn (`[URGENT]`), mã số tuyển dụng (`(2026TD457689)`), giúp JobBERT tập trung vào ngữ nghĩa cốt lõi của chức danh.
   - Ghi nhận `tech_stack_cues` để phục vụ phân tích sâu các chuyên môn hẹp.
4. **Cơ chế mở rộng cho các lần crawl tiếp theo**:
   - Script `scripts/build_title_benchmark.py` cho phép tự động quét các crawl mới, nhận diện title chưa từng xuất hiện, gán cờ `needs_review` để rà soát bán tự động mà không ghi đè lên các nhãn đã duyệt.

## 2. Thống Kê Tổng Quan

- **Tổng số title độc nhất (Unique Titles)**: **87**
- **Tổng số bài tuyển dụng đại diện (Total Postings)**: **89**
- **Tỷ lệ đã rà duyệt (Verified)**: **87 / 87 (100%)**

### Phân Bố Theo Ngôn Ngữ

| Ngôn ngữ | Mã | Số lượng title | Tỷ lệ (%) |
|---|:---:|---:|---:|
| Tiếng Anh | `en` | 41 | 47.1% |
| Việt – Anh kết hợp | `vi-en` | 26 | 29.9% |
| Tiếng Việt thuần | `vi` | 19 | 21.8% |
| Tiếng Hàn (Ngoại lệ) | `ko` | 1 | 1.1% |

### Phân Bố Theo Họ Nghề (Role Family)

| Họ nghề (Role Family) | Số title | Tỷ lệ (%) | Nhóm vai trò |
|---|---:|---:|---|
| **Software Engineering (Backend)** | 11 | 12.6% | IT Cốt lõi (Core IT) |
| **Business Analysis** | 9 | 10.3% | IT Cốt lõi (Core IT) |
| **IT Project Management / Product Management** | 9 | 10.3% | IT Cốt lõi (Core IT) |
| **Software Testing / QA / QC** | 8 | 9.2% | IT Cốt lõi (Core IT) |
| **IT Support & Systems Operations** | 6 | 6.9% | IT Cốt lõi (Core IT) |
| **Data Engineering** | 6 | 6.9% | IT Cốt lõi (Core IT) |
| **IT Operations & Integration Services** | 4 | 4.6% | IT Cốt lõi (Core IT) |
| **IT Architecture & Strategy** | 4 | 4.6% | IT Cốt lõi (Core IT) |
| **Cloud, Systems & Network Infrastructure** | 4 | 4.6% | IT Cốt lõi (Core IT) |
| **DevOps & DevSecOps** | 4 | 4.6% | IT Cốt lõi (Core IT) |
| **Enterprise Applications (ERP / CRM)** | 4 | 4.6% | IT Cốt lõi (Core IT) |
| **Software Engineering (Fullstack / Web)** | 4 | 4.6% | IT Cốt lõi (Core IT) |
| **Information Security / Cybersecurity** | 3 | 3.4% | IT Cốt lõi (Core IT) |
| **IT Sales & Presales** | 3 | 3.4% | IT Ngoại vi / Bán hàng |
| **Database Administration** | 3 | 3.4% | IT Cốt lõi (Core IT) |
| **Software Engineering (AI / ML)** | 1 | 1.1% | IT Cốt lõi (Core IT) |
| **AI / Quantitative Research** | 1 | 1.1% | IT Cốt lõi (Core IT) |
| **IT Translation / Interpretation** | 1 | 1.1% | IT Ngoại vi / Bán hàng |
| **Data Annotation** | 1 | 1.1% | IT Ngoại vi / Bán hàng |
| **Hardware / Verification Engineering** | 1 | 1.1% | IT Cốt lõi (Core IT) |

### Phân Bố Tín Hiệu Cấp Bậc Trong Title (Level Cues)

| Tín hiệu Cấp bậc (Level Cue) | Số title | Ghi chú |
|---|---:|---|
| `Unspecified` | 33 | Tách riêng, không nhập vào họ nghề |
| `Chuyên viên` | 17 | Tách riêng, không nhập vào họ nghề |
| `Manager / Lead` | 8 | Tách riêng, không nhập vào họ nghề |
| `Chuyên viên cao cấp` | 7 | Tách riêng, không nhập vào họ nghề |
| `Senior` | 6 | Tách riêng, không nhập vào họ nghề |
| `Chuyên gia` | 4 | Tách riêng, không nhập vào họ nghề |
| `Nhân viên` | 3 | Tách riêng, không nhập vào họ nghề |
| `Intern` | 1 | Tách riêng, không nhập vào họ nghề |
| `Associate` | 1 | Tách riêng, không nhập vào họ nghề |
| `All Levels` | 1 | Tách riêng, không nhập vào họ nghề |
| `Middle/Senior` | 1 | Tách riêng, không nhập vào họ nghề |
| `Expert/Senior/Middle` | 1 | Tách riêng, không nhập vào họ nghề |
| `Fresher/Junior` | 1 | Tách riêng, không nhập vào họ nghề |
| `Junior` | 1 | Tách riêng, không nhập vào họ nghề |
| `Junior/Middle/Senior` | 1 | Tách riêng, không nhập vào họ nghề |
| `Junior/Senior` | 1 | Tách riêng, không nhập vào họ nghề |

## 3. Danh Mục Mẫu Benchmark (Trích đoạn minh họa)

| ID | Raw Title | Cleaned Title | Ngôn ngữ | Họ nghề (Role Family) | Tín hiệu Level |
|:---:|---|---|:---:|---|:---:|
| `TITLE-001` | AI Engineer | AI Engineer | `en` | **Software Engineering (AI / ML)** | `Unspecified` |
| `TITLE-002` | AI QUANTITATIVE RESEARCHER INTERN (On-site) | AI Quantitative Researcher | `en` | **AI / Quantitative Research** | `Intern` |
| `TITLE-003` | Associate Quality Engineer (Automation) | Quality Engineer (Automation) | `en` | **Software Testing / QA / QC** | `Associate` |
| `TITLE-004` | Business Analyst | Business Analyst | `en` | **Business Analysis** | `Unspecified` |
| `TITLE-005` | C/C++ Software Developer – Telecom (All Levels) | C/C++ Software Developer – Telecom | `en` | **Software Engineering (Backend)** | `All Levels` |
| `TITLE-006` | Chuyên Gia Kiểm Thử & Đánh Giá An Ninh (Pentest) - Hà Nội | Kiểm Thử & Đánh Giá An Ninh (Pentest) | `vi-en` | **Information Security / Cybersecurity** | `Chuyên gia` |
| `TITLE-007` | Chuyên Gia Vận Hành Thẻ | Vận Hành Thẻ | `vi` | **IT Operations & Integration Services** | `Chuyên gia` |
| `TITLE-008` | Chuyên Viên Cao Cấp Vận Hành An Toàn An Ninh Thông Tin - Hà Nội | Vận Hành An Toàn An Ninh Thông Tin | `vi` | **Information Security / Cybersecurity** | `Chuyên viên cao cấp` |
| `TITLE-009` | Chuyên gia Chiến lược công nghệ | Chiến lược công nghệ | `vi` | **IT Architecture & Strategy** | `Chuyên gia` |
| `TITLE-010` | Chuyên gia Kiến trúc doanh nghiệp (EA) | Kiến trúc doanh nghiệp (EA) | `vi-en` | **IT Architecture & Strategy** | `Chuyên gia` |
| `TITLE-011` | Chuyên viên Cao cấp QA | QA | `vi-en` | **Software Testing / QA / QC** | `Chuyên viên cao cấp` |
| `TITLE-012` | Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM | Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM | `vi-en` | **Cloud, Systems & Network Infrastructure** | `Chuyên viên` |
| `TITLE-013` | Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689) | Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số | `vi` | **IT Operations & Integration Services** | `Chuyên viên` |
| `TITLE-014` | Chuyên viên Hỗ trợ bán hàng (Kỹ thuật) | Hỗ trợ bán hàng (Kỹ thuật) | `vi` | **IT Sales & Presales** | `Chuyên viên` |
| `TITLE-015` | Chuyên viên Kinh doanh Cloud, An ninh mạng | Kinh doanh Cloud, An ninh mạng | `vi-en` | **IT Sales & Presales** | `Chuyên viên` |
| `TITLE-016` | Chuyên viên Kiến trúc doanh nghiệp (EA) | Kiến trúc doanh nghiệp (EA) | `vi-en` | **IT Architecture & Strategy** | `Chuyên viên` |
| `TITLE-017` | Chuyên viên Kiểm thử - Tester - Khối Công nghệ thông tin (2026TD456989) | Kiểm thử - Tester | `vi-en` | **Software Testing / QA / QC** | `Chuyên viên` |
| `TITLE-018` | Chuyên viên Phát triển Hệ thống | Phát triển Hệ thống | `vi` | **Software Engineering (Backend)** | `Chuyên viên` |
| `TITLE-019` | Chuyên viên Phân tích nghiệp vụ | Phân tích nghiệp vụ | `vi` | **Business Analysis** | `Chuyên viên` |
| `TITLE-020` | Chuyên viên Phân tích nghiệp vụ (BA) | Phân tích nghiệp vụ (BA) | `vi-en` | **Business Analysis** | `Chuyên viên` |
| `TITLE-021` | Chuyên viên cao cấp Kiểm thử | Kiểm thử | `vi` | **Software Testing / QA / QC** | `Chuyên viên cao cấp` |
| `TITLE-022` | Chuyên viên cao cấp Phát triển Hệ thống | Phát triển Hệ thống | `vi` | **Software Engineering (Backend)** | `Chuyên viên cao cấp` |
| `TITLE-023` | Chuyên viên cao cấp Vận hành hệ thống | Vận hành hệ thống | `vi` | **Cloud, Systems & Network Infrastructure** | `Chuyên viên cao cấp` |
| `TITLE-024` | Chuyên viên cao cấp an ninh mạng | An ninh mạng | `vi` | **Information Security / Cybersecurity** | `Chuyên viên cao cấp` |
| `TITLE-025` | Chuyên viên cao cấp phát triển sản phẩm/giải pháp CNTT | Phát triển sản phẩm/giải pháp CNTT | `vi` | **IT Project Management / Product Management** | `Chuyên viên cao cấp` |

*(Xem toàn bộ 87 title chi tiết trong [data/title_benchmark_v0_1.json](title_benchmark_v0_1.json) và [data/title_benchmark_v0_1.csv](title_benchmark_v0_1.csv))*

## 4. Hướng Dẫn Sử Dụng Cho JobBERT V3

Khi thực hiện gom nhóm title hoặc train classifier với JobBERT V3:
1. **Embedding**: Đưa cả `raw_title` và `cleaned_title` qua JobBERT V3 để so sánh hiệu ứng của việc lọc nhiễu.
2. **Metric đánh giá**:
   - **Clustering**: Silhouette Score, V-Measure, Adjusted Rand Index (ARI) so với nhãn `role_family`.
   - **Classification**: Macro/Weighted F1 Score trên từng họ nghề.
3. **Kiểm tra độ bền vững (Invariance Test)**:
   - Khoảng cách cosine giữa `Data Engineer` và `Senior Data Engineer` phải cực kỳ nhỏ (gần 1.0) về mặt vector họ nghề.
   - Vector embedding của title tiếng Việt (`Chuyên viên Phân tích nghiệp vụ`) và tiếng Anh (`Business Analyst`) phải nằm gần nhau trong không gian đa ngôn ngữ.

## 5. Quy Trình Cập Nhật Title Cho Các Lần Crawl Kế Tiếp

Khi có đợt crawl dữ liệu mới từ TopDev hoặc Saramin:
```powershell
# Quét dữ liệu mới từ database và cập nhật benchmark:
python scripts/build_title_benchmark.py --build

# Kiểm tra các title mới cần duyệt nhãn:
python scripts/build_title_benchmark.py --inspect
```
Các title mới chưa có trong từ điển chuẩn hóa sẽ được đánh dấu `status: needs_review`. Người quản trị rà duyệt nhãn và bổ sung vào `CURATED_TITLE_ANNOTATIONS` trong script để nâng cấp phiên bản benchmark (v0.2...).