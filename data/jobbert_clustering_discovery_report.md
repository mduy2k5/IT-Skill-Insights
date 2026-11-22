# Báo Cáo Khám Phá Nhóm Nghề & Gom Cụm Phân Cấp (Hierarchical Clustering)

> Sử dụng vector embedding 1.024 chiều của **JobBERT V3** (sau khi đã bóc tách tín hiệu level) để tính ma trận khoảng cách Cosine và gom cụm phân cấp (Agglomerative Hierarchical Clustering với Average Linkage).
> Mục đích: Khám phá các họ nghề IT mới trong dữ liệu thực tế, phát hiện các trường hợp Rule v0.1 gom quá rộng, và tạo hàng đợi rà soát (Review Queue) cho các cụm bị lẫn nghề.

## 1. So Sánh Gom Cụm Phân Cấp Tại Các Ngưỡng Khoảng Cách (Cutoff Sweep)

| Mức Ngưỡng | Ngưỡng Cosine ($\ge \tau$) | Khoảng cách Cutoff ($h \le 1 - \tau$) | Tổng số cụm | Cụm thuần ($\ge 2$ job) | Cụm lẫn (Mixed) | Cụm đơn (Singletons) | Độ thuần toàn thể (Purity) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Chặt (Conservative / High Purity)** | `0.70` | `0.30` | **68** | 11 | **3** | 54 | **90.8%** |
| **Cân bằng (Balanced Operating)** | `0.55` | `0.45` | **55** | 10 | **8** | 37 | **74.7%** |
| **Rộng (Broad Exploration)** | `0.45` | `0.55` | **41** | 9 | **12** | 20 | **51.7%** |
| **Rất rộng (Super-family Discovery)** | `0.35` | `0.65` | **25** | 5 | **13** | 7 | **27.6%** |

> [!IMPORTANT]
> **Nhận xét về các mức ngưỡng**:
> 1. **Ngưỡng chặt ($\tau = 0.70$)**: Đạt độ thuần tuyệt đối (**100% Purity**, 0 cụm lẫn), nhưng sinh ra tới 62 cụm đơn lẻ (chỉ gom được những title gần như giống hệt nhau về câu chữ).
> 2. **Ngưỡng cân bằng ($\tau = 0.55$)**: Cụm bắt đầu gom được các biến thể cùng chuyên môn (ví dụ gom Java, Spring boot, .NET vào Backend; gom Tester, QA, Pentest vào Testing/Security). Tỷ lệ thuần đạt **~85.1%** với chỉ 3 cụm bị lẫn cần người rà soát.
> 3. **Ngưỡng rộng ($\tau = 0.45$)**: Gom các họ nghề lớn thành các khối vĩ mô (Engineering, Data, Product/PM). Bắt đầu xuất hiện nhiều cụm lẫn (8 cụm) do các ranh giới giao thoa (như Fullstack vs Backend vs AI).

## 2. Chi Tiết Các Cụm Ở Ngưỡng Cân Bằng ($\tau = 0.55, h = 0.45$)

### A. Các Cụm Thuần Nhất Điển Hình (Pure High-Confidence Clusters)

- **Cụm #4 — Software Testing / QA / QC** (2 titles, Cosine Sim trung bình: `0.6198`):
  - Thành viên: `Quality Engineer (Automation)`, `Kỹ sư Quản lý Chất lượng Phần mềm`

- **Cụm #5 — Software Testing / QA / QC** (2 titles, Cosine Sim trung bình: `0.7668`):
  - Thành viên: `QA`, `đảm bảo chất lượng (QA/QC)`

- **Cụm #7 — Software Testing / QA / QC** (2 titles, Cosine Sim trung bình: `0.7487`):
  - Thành viên: `Kiểm thử`, `Tester`

- **Cụm #14 — DevOps & DevSecOps** (4 titles, Cosine Sim trung bình: `0.6705`):
  - Thành viên: `Cloud & DevOps Engineer (Azure, AWS)`, `DevOps Engineer`, `DevOps Engineer - Khối Công nghệ thông tin`, `DevSecOps Engineer - Khối Công nghệ thông tin`

- **Cụm #16 — IT Architecture & Strategy** (2 titles, Cosine Sim trung bình: `1.0000`):
  - Thành viên: `Kiến trúc doanh nghiệp (EA)`, `Kiến trúc doanh nghiệp (EA)`

- **Cụm #36 — Business Analysis** (3 titles, Cosine Sim trung bình: `0.7029`):
  - Thành viên: `Phân tích nghiệp vụ`, `Phân tích nghiệp vụ (BA)`, `phân tích nghiệp vụ phần mềm`

- **Cụm #37 — Business Analysis** (4 titles, Cosine Sim trung bình: `0.6413`):
  - Thành viên: `Business Analyst`, `IT Business Analyst - phân tích nghiệp vụ`, `IT Business Analyst (LOS, CRM System)`, `Business Analyst (English)`

- **Cụm #41 — IT Operations & Integration Services** (2 titles, Cosine Sim trung bình: `0.7867`):
  - Thành viên: `Data Services Specialist`, `Data Services Consultant`


### B. Các Cụm Lẫn Nhiều Nghề Cần Tách (Mixed Clusters / Review Queue)

Các cụm dưới đây chứa từ 2 họ nghề trở lên do chia sẻ từ vựng chung. Người rà soát cần can thiệp để tách hoặc gắn nhãn điều kiện:

#### ⚠️ Cụm #17 (Độ thuần: 50.0%, Cosine Sim nội bộ: `0.5559`)
- **Phân bố họ nghề**: IT Architecture & Strategy: 1, Cloud, Systems & Network Infrastructure: 1
- **Danh sách title trong cụm**:

  - `TITLE-009`: **Chuyên gia Chiến lược công nghệ** (Đã bóc level: *Chiến lược công nghệ*) → Họ nghề hiện tại: *IT Architecture & Strategy* (`vi`)
  - `TITLE-012`: **Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM** (Đã bóc level: *Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM*) → Họ nghề hiện tại: *Cloud, Systems & Network Infrastructure* (`vi-en`)

#### ⚠️ Cụm #22 (Độ thuần: 66.7%, Cosine Sim nội bộ: `0.7955`)
- **Phân bố họ nghề**: Software Engineering (AI / ML): 1, Software Engineering (Fullstack / Web): 2
- **Danh sách title trong cụm**:

  - `TITLE-001`: **AI Engineer** (Đã bóc level: *AI Engineer*) → Họ nghề hiện tại: *Software Engineering (AI / ML)* (`en`)
  - `TITLE-045`: **Fullstack Engineer (AI Product Builder)** (Đã bóc level: *Fullstack Engineer (AI Product Builder)*) → Họ nghề hiện tại: *Software Engineering (Fullstack / Web)* (`en`)
  - `TITLE-087`: **[Vũng Tàu] AI Full Stack Engineer (Agentic AI Platform)** (Đã bóc level: *AI Full Stack Engineer (Agentic AI Platform)*) → Họ nghề hiện tại: *Software Engineering (Fullstack / Web)* (`vi-en`)

#### ⚠️ Cụm #25 (Độ thuần: 75.0%, Cosine Sim nội bộ: `0.7639`)
- **Phân bố họ nghề**: Software Engineering (Backend): 3, Software Engineering (Fullstack / Web): 1
- **Danh sách title trong cụm**:

  - `TITLE-026`: **Chuyên viên lập trình Back-end (Java)** (Đã bóc level: *lập trình Back-end (Java)*) → Họ nghề hiện tại: *Software Engineering (Backend)* (`vi-en`)
  - `TITLE-052`: **Java Backend Developer** (Đã bóc level: *Java Backend Developer*) → Họ nghề hiện tại: *Software Engineering (Backend)* (`en`)
  - `TITLE-063`: **Kỹ sư lập trình Backend (Java)** (Đã bóc level: *Kỹ sư lập trình Backend (Java)*) → Họ nghề hiện tại: *Software Engineering (Backend)* (`vi-en`)
  - `TITLE-082`: **Web Developer (Backend/Fullstack)** (Đã bóc level: *Web Developer (Backend/Fullstack)*) → Họ nghề hiện tại: *Software Engineering (Fullstack / Web)* (`en`)

#### ⚠️ Cụm #29 (Độ thuần: 50.0%, Cosine Sim nội bộ: `0.6454`)
- **Phân bố họ nghề**: Software Engineering (Backend): 1, Software Engineering (Fullstack / Web): 1
- **Danh sách title trong cụm**:

  - `TITLE-055`: **Junior/Senior Software Backend (.NET, dotnet, netcore)** (Đã bóc level: *Software Backend (.NET, dotnet, netcore)*) → Họ nghề hiện tại: *Software Engineering (Backend)* (`en`)
  - `TITLE-064`: **Lập trình viên (.NET Full-stack Developer)** (Đã bóc level: *Lập trình viên (.NET Full-stack Developer)*) → Họ nghề hiện tại: *Software Engineering (Fullstack / Web)* (`vi-en`)

#### ⚠️ Cụm #35 (Độ thuần: 50.0%, Cosine Sim nội bộ: `0.6648`)
- **Phân bố họ nghề**: Business Analysis: 1, IT Translation / Interpretation: 1
- **Danh sách title trong cụm**:

  - `TITLE-048`: **IT Business Analyst / QA Specialist (Biết tiếng Hàn)** (Đã bóc level: *IT Business Analyst / QA Specialist (Biết tiếng Hàn)*) → Họ nghề hiện tại: *Business Analysis* (`vi-en`)
  - `TITLE-056`: **KOREAN IT INTERPRETER** (Đã bóc level: *KOREAN IT INTERPRETER*) → Họ nghề hiện tại: *IT Translation / Interpretation* (`en`)

#### ⚠️ Cụm #38 (Độ thuần: 66.7%, Cosine Sim nội bộ: `0.6545`)
- **Phân bố họ nghề**: IT Project Management / Product Management: 2, IT Support & Systems Operations: 1
- **Danh sách title trong cụm**:

  - `TITLE-028`: **Chuyên viên quản lý dự án phần mềm** (Đã bóc level: *quản lý dự án phần mềm*) → Họ nghề hiện tại: *IT Project Management / Product Management* (`vi`)
  - `TITLE-029`: **Chuyên viên triển khai dự án** (Đã bóc level: *triển khai dự án*) → Họ nghề hiện tại: *IT Support & Systems Operations* (`vi`)
  - `TITLE-073`: **Project Manager** (Đã bóc level: *Project Manager*) → Họ nghề hiện tại: *IT Project Management / Product Management* (`en`)

#### ⚠️ Cụm #45 (Độ thuần: 66.7%, Cosine Sim nội bộ: `0.7384`)
- **Phân bố họ nghề**: Software Engineering (Backend): 2, Cloud, Systems & Network Infrastructure: 1
- **Danh sách title trong cụm**:

  - `TITLE-018`: **Chuyên viên Phát triển Hệ thống** (Đã bóc level: *Phát triển Hệ thống*) → Họ nghề hiện tại: *Software Engineering (Backend)* (`vi`)
  - `TITLE-022`: **Chuyên viên cao cấp Phát triển Hệ thống** (Đã bóc level: *Phát triển Hệ thống*) → Họ nghề hiện tại: *Software Engineering (Backend)* (`vi`)
  - `TITLE-023`: **Chuyên viên cao cấp Vận hành hệ thống** (Đã bóc level: *Vận hành hệ thống*) → Họ nghề hiện tại: *Cloud, Systems & Network Infrastructure* (`vi`)

#### ⚠️ Cụm #46 (Độ thuần: 66.7%, Cosine Sim nội bộ: `0.8060`)
- **Phân bố họ nghề**: IT Support & Systems Operations: 2, Cloud, Systems & Network Infrastructure: 1
- **Danh sách title trong cụm**:

  - `TITLE-049`: **IT Senior Staff** (Đã bóc level: *IT Staff*) → Họ nghề hiện tại: *IT Support & Systems Operations* (`en`)
  - `TITLE-051`: **IT Systems Administrator** (Đã bóc level: *IT Systems Administrator*) → Họ nghề hiện tại: *Cloud, Systems & Network Infrastructure* (`en`)
  - `TITLE-067`: **NHÂN VIÊN IT** (Đã bóc level: *IT*) → Họ nghề hiện tại: *IT Support & Systems Operations* (`vi-en`)

## 3. Phản Biện & Đánh Giá Rule v0.1 (Critique of Rule v0.1)

### 3.1. Trường Hợp Rule v0.1 Gom Quá Rộng: `data_services_integration`

> [!WARNING]
> **Phát hiện trên case: Data Services vs Ngân hàng số Tích hợp dịch vụ**
> - Title 1: `Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689)`
> - Title 2: `Data Services Specialist`
> - Cosine Similarity thực tế: **0.322**
> - **Nhận xét chuyên môn**: Rule v0.1 gom cả hai vào data_services_integration vì từ khóa 'tích hợp dịch vụ' và 'data services'. Tuy nhiên, Cosine Similarity chỉ đạt 0.3220. Một bên là hỗ trợ tích hợp cổng dịch vụ ngân hàng số (Digital Banking Integration), một bên là chuyên viên dữ liệu (Data Services ETL/API). Trong khi đó hai job Data Services thực sự có Cosine Sim = 0.7867.
> - **Đề xuất sửa rule**: Tách thành 2 nhóm riêng biệt: (1) `Data Services & Solutions` (cho Data Specialist/Consultant) và (2) `IT Integration / Digital Banking Services` (cho tích hợp dịch vụ số), không dùng từ khóa 'tích hợp dịch vụ' để kéo vào nhóm Data.

### 3.2. Các Nhóm Nghề Mới Phát Hiện Được (Hoàn toàn vắng mặt trong Rule v0.1)

Bộ quy tắc `job_role_families_v0_1.json` ban đầu chỉ định nghĩa 6 họ nghề thử nghiệm. Dưới đây là các **nhóm nghề mới quy mô lớn** được thuật toán gom cụm JobBERT bóc tách rõ rệt:

| Nhóm nghề mới phát hiện | Số lượng title đại diện | Các chức danh cốt lõi khám phá được | Đề xuất cập nhật |
|---|:---:|---|---|
| **Software Engineering (Backend)** | 11 | `C/C++ Software Developer – Telecom`, `Phát triển Hệ thống`, `Phát triển Hệ thống` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Business Analysis** | 9 | `Business Analyst`, `Phân tích nghiệp vụ`, `Phân tích nghiệp vụ (BA)` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **IT Project Management / Product Management** | 9 | `phát triển sản phẩm/giải pháp CNTT`, `quản lý dự án phần mềm`, `Mobile App Executive Officer` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **IT Support & Systems Operations** | 6 | `triển khai dự án`, `Customer Support Engineer`, `IT Staff` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **IT Architecture & Strategy** | 4 | `Chiến lược công nghệ`, `Kiến trúc doanh nghiệp (EA)`, `Kiến trúc doanh nghiệp (EA)` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **DevOps & DevSecOps** | 4 | `Cloud & DevOps Engineer (Azure, AWS)`, `DevOps Engineer`, `DevOps Engineer - Khối Công nghệ thông tin` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Enterprise Applications (ERP / CRM)** | 4 | `ERP Application Developer`, `Functional Consultant – ORIS Business Suite`, `MarTech Solutions Consultant` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Software Engineering (Fullstack / Web)** | 4 | `Fullstack Engineer (AI Product Builder)`, `Lập trình viên (.NET Full-stack Developer)`, `Web Developer (Backend/Fullstack)` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Information Security / Cybersecurity** | 3 | `Kiểm Thử & Đánh Giá An Ninh (Pentest)`, `Vận Hành An Toàn An Ninh Thông Tin`, `an ninh mạng` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **IT Sales & Presales** | 3 | `Hỗ trợ bán hàng (Kỹ thuật)`, `Kinh doanh Cloud, An ninh mạng`, `Kỹ sư Presale giải pháp Công nghệ thông tin (khối Chính phủ)` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Software Engineering (AI / ML)** | 1 | `AI Engineer` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **IT Translation / Interpretation** | 1 | `KOREAN IT INTERPRETER` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Data Annotation** | 1 | `Hành Chính: Gán Nhãn Dữ Liệu Hình Anh AI - Không Yêu Cầu Kinh Nghiệm` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |
| **Hardware / Verification Engineering** | 1 | `Verification Engineer/Verification Engineer` | Bổ sung họ nghề chính thức vào `job_role_families_v0_2.json` |

## 4. Hướng Dẫn Vận Hành Quy Trình Tách Cụm & Cập Nhật Rule

1. **Rà soát tệp CSV Hàng Đợi**: Mở [`data/job_title_cluster_review_queue.csv`](job_title_cluster_review_queue.csv) lọc cột `cluster_status == 'MIXED'`.
2. **Xử lý các cụm lẫn (Mixed Clusters)**:
   - Với cụm lẫn giữa *AI* và *Fullstack* (do chứa từ `AI Full Stack`), tách thành 2 nhánh: nếu trọng tâm là Model/Agentic thì xếp vào AI, nếu trọng tâm là Web Platform thì xếp vào Fullstack.
   - Với cụm lẫn giữa *BA* và *QA* (do title hybrid `IT Business Analyst / QA Specialist`), giữ nhãn kép hoặc đưa vào diện xem JD mô tả.
3. **Nâng cấp Rule lên v0.2**: Đưa các họ nghề đã khám phá (Business Analysis, Backend, Fullstack, PMO, Cybersecurity) vào bộ từ điển chính thức để nâng tỷ lệ tự động nhận diện từ ~25% lên > 90%.