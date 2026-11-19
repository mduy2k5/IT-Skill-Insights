# Feature Specification: Nền tảng việc làm IT

**Feature Branch**: `Not created; existing worktree retained`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: Xây dựng nền tảng việc làm IT, bắt đầu với job Data trên TopDev, thu thập lịch sử theo từng giai đoạn, giữ thông tin cơ bản và mô tả công việc, hiển thị job trên website, rồi mở rộng sang nhiều website khác theo các nguồn độc lập. Phân tích kỹ năng cần thiết theo trình độ, ưu tiên chi phí miễn phí và giới hạn truy cập để không gây tải quá mức.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Thu thập dữ liệu lịch sử theo từng giai đoạn (Priority: P1)

Người vận hành muốn chọn nguồn và khoảng thời gian để thu thập job theo các giai đoạn nhỏ, theo dõi phần đã làm và tiếp tục sau khi bị gián đoạn. Việc này tạo nền dữ liệu cho website và phân tích sau này.

**Why this priority**: Nền tảng cần dữ liệu lịch sử nhưng không thể thu thập toàn bộ trong một lượt. Tiến độ phải có thể tiếp tục mà không bỏ sót giai đoạn hoặc tạo bản sao.

**Independent Test**: Chọn một nguồn và ít nhất ba khoảng thời gian có dữ liệu, chạy một phần, mô phỏng gián đoạn, tiếp tục phần còn lại; đối chiếu nguồn, khoảng thời gian, số job và định danh của từng job.

**Acceptance Scenarios**:

1. **Given** người vận hành chọn một nguồn và khoảng thời gian, **When** hệ thống xử lý khoảng đó thành các giai đoạn nhỏ, **Then** mỗi giai đoạn có trạng thái và số liệu riêng, và job giữ được nguồn cùng liên kết gốc.
2. **Given** một lượt thu thập bị gián đoạn giữa các giai đoạn, **When** người vận hành tiếp tục, **Then** hệ thống xử lý giai đoạn chưa hoàn tất và không tạo job trùng cho dữ liệu đã lưu.
3. **Given** nguồn không có dữ liệu trong một giai đoạn hoặc giới hạn truy cập, **When** giai đoạn kết thúc, **Then** kết quả được ghi là rỗng, tạm dừng hoặc lỗi phù hợp thay vì báo thành công giả.

---

### User Story 2 - Tìm và xem job IT, ưu tiên Data (Priority: P1)

Người tìm việc muốn duyệt các job IT, lọc để tìm vai trò Data phù hợp và đọc mô tả đầy đủ trước khi tự quyết định xem tin đó có liên quan hay không.

**Why this priority**: Website là bề mặt sản phẩm chính để biến dữ liệu thu thập được thành giá trị trực tiếp cho người dùng.

**Independent Test**: Nạp một bộ job mẫu có vai trò Data và các vai trò IT khác; tìm theo từ khóa, lọc theo trình độ hoặc địa điểm, rồi mở trang chi tiết và đối chiếu thông tin với bản ghi nguồn.

**Acceptance Scenarios**:

1. **Given** đã có job IT được thu thập, **When** người dùng duyệt hoặc tìm theo từ khóa và bộ lọc, **Then** danh sách chỉ hiển thị job khớp điều kiện và hỗ trợ tập trung vào nhóm Data.
2. **Given** người dùng mở một job, **When** nội dung chi tiết khả dụng, **Then** trang chi tiết hiển thị các trường cơ bản và mô tả công việc đã thu thập.
3. **Given** nguồn không cung cấp mô tả hoặc lần tải mô tả chưa hoàn tất, **When** người dùng xem job, **Then** trang thể hiện rõ tình trạng mô tả thay vì trình bày như nội dung đầy đủ.

---

### User Story 3 - Xem nhu cầu kỹ năng theo trình độ (Priority: P2)

Người tìm việc và người phân tích thị trường muốn hiểu kỹ năng nào thường được yêu cầu trong mô tả công việc và cách nhu cầu đó khác nhau theo trình độ.

**Why this priority**: Phân tích kỹ năng là giá trị khác biệt của nền tảng, đồng thời phụ thuộc vào chất lượng và độ phủ của mô tả công việc đã thu thập.

**Independent Test**: Dùng một tập mô tả công việc đã được rà soát, chạy phân tích cho một khoảng thời gian và đối chiếu các nhóm trình độ, số job được phân tích, kỹ năng được nêu và bằng chứng trong mô tả.

**Acceptance Scenarios**:

1. **Given** có mô tả công việc và thông tin trình độ, **When** người dùng xem thống kê cho một giai đoạn, **Then** hệ thống nhóm nhu cầu kỹ năng theo trình độ và hiển thị số job làm mẫu số của từng nhóm.
2. **Given** mô tả thiếu, trình độ chưa rõ hoặc kết quả phân tích không chắc chắn, **When** thống kê được tạo, **Then** hệ thống thể hiện phần chưa phân loại và cho phép truy ngược kết quả kỹ năng về nội dung job hỗ trợ nó.

---

### User Story 4 - Mở rộng sang nhiều website độc lập (Priority: P2)

Người vận hành muốn bổ sung thêm website tuyển dụng và website tổng hợp job theo từng nguồn riêng, để lỗi truy cập hoặc thay đổi cấu trúc ở một nguồn không làm dừng việc thu thập từ các nguồn còn hoạt động.

**Why this priority**: Độ phủ thị trường tăng khi thêm nguồn, nhưng mỗi nguồn có cách truy cập và cấu trúc khác nhau. Cô lập trạng thái từng nguồn giúp mở rộng mà không làm mất tiến độ của nguồn khác.

**Independent Test**: Cấu hình ít nhất hai nguồn thử nghiệm, làm một nguồn lỗi có kiểm soát và xác nhận nguồn còn lại vẫn hoàn tất, có kết quả cùng trạng thái riêng.

**Acceptance Scenarios**:

1. **Given** có ít nhất hai nguồn đã cấu hình, **When** một nguồn lỗi hoặc bị giới hạn, **Then** nguồn khác vẫn được xử lý và báo cáo kết quả độc lập.
2. **Given** một website mới được thêm, **When** website đó thu thập job, **Then** job được lưu theo hợp đồng thông tin chung và vẫn truy nguyên được nguồn gốc riêng.

## Edge Cases

- Nguồn không lưu hoặc không cho truy cập các tin cũ trong một số giai đoạn lịch sử.
- Giai đoạn đã xử lý nhưng nguồn thay đổi hoặc xóa tin trước khi lần thu thập tiếp theo diễn ra.
- Một giai đoạn có 0 job hợp lệ; cần phân biệt với lỗi truy cập, lỗi phân tích hoặc lỗi lưu dữ liệu.
- Danh sách job có dữ liệu cơ bản nhưng trang chi tiết rỗng, bị gỡ, yêu cầu đăng nhập hoặc bị chặn.
- Nguồn trả tín hiệu giới hạn tốc độ hoặc yêu cầu xác thực; hệ thống phải giảm tốc hoặc tạm dừng.
- Job có trình độ không nằm trong bộ nhóm đã thống nhất hoặc không có trường trình độ.
- Nội dung mô tả chứa kỹ năng viết bằng nhiều biến thể, hoặc AI không thể đưa ra kết quả đủ tin cậy.
- Hạn mức miễn phí sắp hết hoặc dịch vụ dự kiến phát sinh chi phí.
- Một website thay đổi HTML, chặn truy cập hoặc tạm ngừng trong khi các nguồn khác vẫn hoạt động.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Nguồn đầu tiên MUST là trang job Data TopDev do người dùng chỉ định tại `https://topdev.vn/jobs/search?job_categories_ids=8`. Hệ thống MUST hỗ trợ backfill toàn bộ lịch sử mà nguồn cho phép truy cập đến hiện tại, chia theo năm, tháng hoặc khoảng thời gian nhỏ do người vận hành chọn.
- **FR-002**: Hệ thống MUST lưu trạng thái và số liệu cho từng giai đoạn, phân biệt hoàn tất, rỗng, đang xử lý, tạm dừng và thất bại.
- **FR-003**: Người vận hành MUST có thể tiếp tục các giai đoạn chưa hoàn tất sau gián đoạn; chạy lại dữ liệu đã xử lý MUST NOT tạo bản sao job cùng nguồn và cùng định danh/link hiện hành.
- **FR-004**: Mỗi job MUST lưu nguồn truy vết, link gốc và các thông tin cơ bản có sẵn như tiêu đề, công ty, địa điểm, lương, loại việc, trình độ, ngày đăng và tags; trường không có dữ liệu MUST được thể hiện là chưa biết hoặc chưa có.
- **FR-005**: Hệ thống MUST thu thập và giữ mô tả công việc khi nguồn cung cấp; trạng thái tải chi tiết MUST được phân biệt với trạng thái tin danh sách để mô tả rỗng do lỗi hoặc chưa tải không bị coi là hoàn tất.
- **FR-006**: Website MUST cho người dùng duyệt và tìm job IT, với cách khám phá nhóm Data được ưu tiên trong trải nghiệm ban đầu.
- **FR-007**: Website MUST cho phép mở trang chi tiết job và phân biệt mô tả đầy đủ, chưa có, chưa tải xong hoặc không truy cập được.
- **FR-008**: Hệ thống MUST phân tích mô tả job để thống kê kỹ năng cần thiết theo trình độ và khoảng thời gian; MUST chuẩn hóa nhãn trình độ khác nhau từ từng nguồn thành các nhóm chung và giữ riêng nhóm chưa rõ.
- **FR-009**: Thống kê kỹ năng MUST hiển thị số job được phân tích làm mẫu số, phần job chưa phân loại và bằng chứng từ mô tả công việc cho các kỹ năng được báo cáo.
- **FR-010**: Hệ thống MUST phân biệt giai đoạn thu thập rỗng hợp lệ với lỗi truy cập, xác thực, phân tích nội dung và lưu dữ liệu.
- **FR-011**: Hệ thống MUST áp dụng giới hạn truy cập thấp và cấu hình riêng theo từng nguồn, không tạo đợt truy cập dồn dập, và MUST giảm tốc hoặc tạm dừng khi nguồn báo giới hạn hoặc chặn truy cập.
- **FR-012**: MVP MUST không phát sinh chi phí. Khi dịch vụ chạm hoặc sắp chạm hạn mức miễn phí, hệ thống MUST tạm dừng hoặc chờ hạn mức được khôi phục và MUST NOT chuyển sang dịch vụ trả phí.
- **FR-013**: Hệ thống MUST thể hiện phạm vi dữ liệu đã thu thập theo nguồn và giai đoạn để người dùng biết phần nào đã hoàn tất, rỗng, chưa truy cập được hoặc còn thiếu.
- **FR-014**: Mỗi nguồn MUST có trạng thái và chính sách thu thập độc lập; lỗi hoặc giới hạn ở một nguồn MUST NOT ngăn các nguồn khác tiếp tục xử lý và báo cáo kết quả riêng.
- **FR-015**: Việc bổ sung website MUST giữ hợp đồng thông tin chung của job cùng truy vết nguồn gốc; nguồn mới MUST được đánh giá riêng về khả năng truy cập và giới hạn trước khi bật thu thập.

### Key Entities *(include if feature involves data)*

- **Nguồn việc làm**: Website hoặc nguồn dữ liệu có tên/định danh, chính sách truy cập và giới hạn thu thập riêng.
- **Giai đoạn thu thập**: Khoảng lịch sử được chọn để xử lý, có trạng thái, số liệu và khả năng tiếp tục.
- **Job**: Tin tuyển dụng có nguồn, link/định danh gốc, thông tin cơ bản, trình độ và trạng thái vòng đời.
- **Mô tả công việc**: Nội dung chi tiết của job cùng trạng thái và thời điểm thu thập.
- **Kết quả kỹ năng**: Kỹ năng được suy ra từ mô tả, nhóm trình độ, số job làm mẫu số và bằng chứng truy nguyên.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% giai đoạn lịch sử được yêu cầu có trạng thái kết thúc hoặc trạng thái chờ rõ ràng cùng số job đã xử lý; kết quả rỗng được phân biệt với lỗi.
- **SC-002**: Trong kịch bản kiểm chứng gồm ít nhất ba giai đoạn có một lần gián đoạn, hệ thống tiếp tục từ phần chưa hoàn tất và sau khi chạy lại vẫn chỉ có một bản ghi cho mỗi job cùng nguồn và định danh/link.
- **SC-003**: 100% job trong bộ kiểm chứng có trường cơ bản và mô tả lấy được từ nguồn đều có thể xem trên website; trường không lấy được được chỉ rõ thay vì hiển thị như dữ liệu đầy đủ.
- **SC-004**: Với bộ dữ liệu kiểm chứng và bộ lọc đã định trước, mọi job Data khớp điều kiện đều xuất hiện, job không khớp bị loại khỏi kết quả, và mỗi kết quả đều mở được trang chi tiết tương ứng.
- **SC-005**: Với mọi thống kê kỹ năng được hiển thị, tổng số job làm mẫu số và số lượng từng kỹ năng khớp với các kết quả phân tích được lưu; mỗi kỹ năng có thể truy nguyên về ít nhất một đoạn mô tả hỗ trợ.
- **SC-006**: Trong mọi lượt thu thập kiểm chứng, số yêu cầu không vượt giới hạn cấu hình của nguồn; khi nhận tín hiệu giới hạn/chặn, hệ thống giảm tốc hoặc dừng theo chính sách đã cấu hình.
- **SC-007**: Chi phí vận hành MVP bằng 0; khi chạm hạn mức miễn phí, xử lý tạm dừng hoặc chờ thay vì phát sinh khoản phí.
- **SC-008**: Trong lượt kiểm chứng có ít nhất hai nguồn, khi một nguồn bị lỗi có kiểm soát, mọi nguồn còn lại vẫn kết thúc với trạng thái và số liệu riêng; lỗi của nguồn thứ nhất không làm mất kết quả của nguồn thứ hai.

## Assumptions

- Phạm vi ban đầu là website job IT tập trung vào Data; nền tảng vẫn lưu được các nhóm IT khác để mở rộng sau.
- Nguồn đầu tiên là trang Data trên TopDev tại URL do người dùng cung cấp. TopCV, VietnamWorks, Vietlamtot và các website tổng hợp như Xomdata là các ứng viên mở rộng được người dùng nêu; URL và khả năng thu thập của từng nguồn cần xác nhận riêng.
- Việc mở rộng nguồn diễn ra từng website một; chưa có số lượng nguồn cuối cùng được chốt.
- Phạm vi backfill là toàn bộ tin lịch sử mà nguồn thực sự còn cung cấp; không giả định TopDev lưu trữ hoặc cho phép truy cập mọi tin đã đăng.
- Người dùng đầu tiên gồm người tìm việc và người xem phân tích nhu cầu kỹ năng; đăng tuyển, ứng tuyển trực tiếp, hồ sơ cá nhân và gợi ý job cá nhân chưa thuộc phạm vi MVP.
- Mỗi lượt backfill chỉ xử lý các giai đoạn được chọn; không giả định một nguồn còn lưu toàn bộ lịch sử hoặc cho phép truy cập mọi tin cũ.
- Chỉ thu thập theo cách nguồn cho phép. Nếu nguồn không công bố giới hạn, cần dùng cấu hình thận trọng; gặp 429, 403, trang đăng nhập hoặc tín hiệu chặn thì giảm tốc hoặc dừng, không tìm cách vượt bảo vệ.
- MVP có ngân sách tuyệt đối 0; khi hết hạn mức miễn phí, khối lượng công việc phải chờ hoặc tạm dừng. Các hạn mức dịch vụ cần được kiểm tra ở bước lập kế hoạch.
- Job từ nguồn khác nhau được lưu có truy vết riêng; chỉ gộp tin tương đương khi có quy tắc và bằng chứng phù hợp.
- Kết quả AI là thống kê hỗ trợ tham khảo từ mô tả công việc, không thay thế lời khuyên nghề nghiệp hoặc quyết định tuyển dụng.
- Nhà cung cấp dịch vụ và công cụ tự động hóa được quyết định ở bước plan sau khi kiểm tra hạn mức miễn phí và khả năng đáp ứng yêu cầu.
