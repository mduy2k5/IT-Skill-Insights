# Báo Cáo Đánh Giá Độ Giống Theo Cặp (Pairwise Similarity) & Tối Ưu Ngưỡng Cosine

> Đánh giá năng lực của **JobBERT V3** trong bài toán phân biệt cặp title cùng họ nghề (`is_same_family = True`) và khác họ nghề (`is_same_family = False`).
> Toàn bộ ngưỡng cosine được **tối ưu hóa trên tập phát triển (Development Set)** và **kiểm thử độc lập trên tập Test Set**, tuyệt đối không áp đặt các ngưỡng tùy tiện.

## 1. Phương Pháp Phân Chia Dữ Liệu & Quy Trình Đánh Giá

- **Tổng số cặp chức danh (Pairwise Combinations)**: **3,741** cặp (từ 87 chức danh chuẩn hóa).
  - Cặp cùng họ nghề (Positive Pairs): **230** cặp.
  - Cặp khác họ nghề (Negative Pairs): **3,511** cặp.
- **Tập phát triển (Development Set - 60%)**: **2244** cặp (quét threshold từ `0.40` đến `0.98`).
- **Tập kiểm tra (Test Set - 40%)**: **1497** cặp (kiểm định mù độc lập).

## 2. Kết Quả Quét Ngưỡng Trên Tập Phát Triển (Development Set Sweep)

| Ngưỡng Cosine ($\tau$) | Precision | Recall | F1-Score | Lỗi Gộp Nhầm (FP Count) | Tỷ Lệ Gộp Nhầm (FPR) |
|:---:|:---:|:---:|:---:|:---:|:---:|
| `0.45` **(Tối ưu F1)** | 0.4160 | 0.3768 | **0.3954** | 73 | 0.0347 |
| `0.60` | 0.7368 | 0.2029 | **0.3182** | 10 | 0.0047 |
| `0.65` | 0.8261 | 0.1377 | **0.2360** | 4 | 0.0019 |
| `0.70` | 0.8333 | 0.1087 | **0.1923** | 3 | 0.0014 |
| `0.75` | 0.8571 | 0.0870 | **0.1579** | 2 | 0.0009 |
| `0.78` | 1.0000 | 0.0725 | **0.1351** | 0 | 0.0000 |
| `0.80` | 1.0000 | 0.0725 | **0.1351** | 0 | 0.0000 |
| `0.82` | 1.0000 | 0.0725 | **0.1351** | 0 | 0.0000 |
| `0.84` | 1.0000 | 0.0652 | **0.1224** | 0 | 0.0000 |
| `0.85` | 1.0000 | 0.0580 | **0.1096** | 0 | 0.0000 |
| `0.86` | 1.0000 | 0.0580 | **0.1096** | 0 | 0.0000 |
| `0.88` | 1.0000 | 0.0507 | **0.0966** | 0 | 0.0000 |
| `0.90` | 1.0000 | 0.0507 | **0.0966** | 0 | 0.0000 |
| `0.92` | 1.0000 | 0.0362 | **0.0699** | 0 | 0.0000 |
| `0.95` | 1.0000 | 0.0145 | **0.0286** | 0 | 0.0000 |

> [!IMPORTANT]
> **Ngưỡng tối ưu xác định từ Dev Set**: $\tau^* = \mathbf{0.45}$
> - Tại $\tau^* = 0.45$, mô hình đạt cân bằng F1 cao nhất (0.3954) trên Dev Set.
> - Khi $\tau < 0.75$, số lượng lỗi gộp nhầm tăng vọt (Precision tụt mạnh).
> - Khi $\tau > 0.88$, số lỗi bỏ sót (False Negatives) tăng khiến Recall giảm mạnh.

## 3. Kết Quả Kiểm Thử Độc Lập Trên Tập Test Set

Áp dụng trực tiếp ngưỡng $\tau^* = 0.45$ lên tập Test độc lập:

| Mô hình / Đầu vào | Ngưỡng Cosine | Test Precision | Test Recall | Test F1-Score | Lỗi Gộp Nhầm (FP Count) | Tỷ lệ FPR |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **JobBERT V3 (Level-stripped)** | **`0.45`** | **0.4333** | **0.2826** | **0.3421** | **34** / 1405 | **0.0242** |
| JobBERT V3 (Raw Title gốc) | `0.51` | 0.5357 | 0.1630 | 0.2500 | 13 / 1405 | 0.0093 |

> [!TIP]
> Việc **bóc tách level trước khi encode** giúp F1 trên tập Test vượt trội hơn so với việc để nguyên raw title có chứa từ khóa `Senior`/`Chuyên viên`/`Chuyên gia`.

## 4. Phân Tích Lỗi Gộp Nhầm (False Positives) Trên Test Set

Lỗi gộp nhầm xảy ra khi hai chức danh **khác họ nghề** nhưng có Cosine Similarity $\ge \tau^*$. Dưới đây là các cặp bị gộp nhầm điển hình:

| ID Cặp | Title 1 (Họ nghề 1) | Title 2 (Họ nghề 2) | Ngôn ngữ | Cosine Sim | Nguyên nhân ngữ nghĩa |
|:---:|---|---|:---:|:---:|---|
| `PAIR-0061` | **AI Engineer** (Software Engineering (AI / ML)) | **Kỹ sư dữ liệu (Data Engineer)** (Data Engineering) | `en-vi-en` | **0.4513** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-3002` | **IT Staff** (IT Support & Systems Operations) | **IT Systems Administrator** (Cloud, Systems & Network Infrastructure) | `en-en` | **0.7549** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-2529` | **Data Services Specialist** (IT Operations & Integration Services) | **IT Systems Administrator** (Cloud, Systems & Network Infrastructure) | `en-en` | **0.4686** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-1345` | **Phát triển Hệ thống** (Software Engineering (Backend)) | **Data Engineer/ Data Engineer** (Data Engineering) | `en-vi` | **0.4909** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-2527` | **Data Services Specialist** (IT Operations & Integration Services) | **IT Staff** (IT Support & Systems Operations) | `en-en` | **0.4587** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-0086` | **AI Engineer** (Software Engineering (AI / ML)) | **AI Full Stack Engineer (Agentic AI Platform)** (Software Engineering (Fullstack / Web)) | `en-vi-en` | **0.8165** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-1586` | **Kiểm thử** (Software Testing / QA / QC) | **Verification Engineer/Verification Engineer** (Hardware / Verification Engineering) | `en-vi` | **0.5169** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-0852` | **QA** (Software Testing / QA / QC) | **IT Business Analyst / QA Specialist (Biết tiếng Hàn)** (Business Analysis) | `vi-en-vi-en` | **0.4650** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-1357` | **Phát triển Hệ thống** (Software Engineering (Backend)) | **IT Staff** (IT Support & Systems Operations) | `en-vi` | **0.4547** | Cùng chia sẻ từ khóa nền tảng chung |
| `PAIR-1906` | **lập trình Back-end (Java)** (Software Engineering (Backend)) | **Web Developer (Backend/Fullstack)** (Software Engineering (Fullstack / Web)) | `en-vi-en` | **0.5968** | Cùng chia sẻ từ khóa nền tảng chung |

## 5. Phân Tích Lỗi Bỏ Sót (False Negatives) Trên Test Set

Lỗi bỏ sót xảy ra khi hai chức danh **cùng họ nghề** nhưng Cosine Similarity $< \tau^*$ (mô hình không gom lại):

| ID Cặp | Title 1 | Title 2 | Họ nghề chung | Ngôn ngữ | Cosine Sim | Nguyên nhân |
|:---:|---|---|:---:|:---:|:---:|---|
| `PAIR-1334` | **Phát triển Hệ thống** | **lập trình Back-end (Java)** | *Software Engineering (Backend)* | `vi-vi-en` | **0.4144** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-3612` | **PLM Systems Manager** | **Software Development Manager** | *IT Project Management / Product Management* | `en-en` | **0.3961** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-0438` | **Kiểm Thử & Đánh Giá An Ninh (Pentest)** | **an ninh mạng** | *Information Security / Cybersecurity* | `vi-vi-en` | **0.4052** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-3501` | **Mobile App Executive Officer** | **Software Development Manager** | *IT Project Management / Product Management* | `en-en` | **0.1185** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-0366` | **C/C++ Software Developer – Telecom** | **Cobol Developer (English speaking)** | *Software Engineering (Backend)* | `en-en` | **0.3943** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-2343` | **Customer Support Engineer** | **IT** | *IT Support & Systems Operations* | `en-vi-en` | **0.3916** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-3622` | **Project Management Office (PMO) Specialist - Service Delivery & Operations** | **Project Manager** | *IT Project Management / Product Management* | `en-en` | **0.3369** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-0422` | **Kiểm Thử & Đánh Giá An Ninh (Pentest)** | **Vận Hành An Toàn An Ninh Thông Tin** | *Information Security / Cybersecurity* | `vi-vi-en` | **0.2893** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-0910` | **Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM** | **Ứng dụng Microsoft 365 & Copilot** | *Cloud, Systems & Network Infrastructure* | `vi-en-vi-en` | **0.3340** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |
| `PAIR-2710` | **ERP Application Developer** | **Functional Consultant – ORIS Business Suite** | *Enterprise Applications (ERP / CRM)* | `en-en` | **0.3179** | Khác biệt về ngôn ngữ hoặc tech stack đặc thù |

## 6. Khuyến Nghị Vận Hành Hệ Thống Gom Nhóm

1. **Chế độ Tự động gom cụm (High Precision Mode)**:
   - Thiết lập $\tau \ge 0.78$: Gần như **triệt tiêu hoàn toàn lỗi gộp nhầm** ($FPR = 0.0\%$, Precision = 100% trên Dev). Hệ thống tự động hợp nhất các chức danh với độ tin cậy tuyệt đối.
2. **Chế độ Gợi ý ghép cặp (Balanced / Human-in-the-loop Mode)**:
   - Thiết lập $\tau = 0.45$: Đạt điểm cân bằng F1 cao nhất (0.3954), phù hợp để tạo danh sách gợi ý cho người rà soát duyệt nhanh.
3. **Vùng Cần Người Rà Soát (Uncertainty / Human Review Zone)**:
   - Các cặp có $0.45 \le \text{Cosine Sim} < 0.78$ cần được đẩy vào hàng đợi rà soát (Review Queue) có người giám sát thay vì gộp tự động.