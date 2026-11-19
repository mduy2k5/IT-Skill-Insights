# Đặc tả tính năng: Độ tin cậy của lượt ETL

**Feature Branch**: `Not created; existing worktree retained`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: Make the existing job transformation pipeline report failures and process dependent mappings only after job records are loaded.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tin cậy trạng thái lượt chạy (Priority: P1)

Người vận hành cần biết một lượt xử lý dữ liệu đã hoàn tất, không có dữ liệu mới, hay thất bại ở bước nào để quyết định có thể dùng dữ liệu cho báo cáo hay cần xử lý lỗi.

**Why this priority**: Nhật ký hiện tại có thể cho thấy Airflow thành công dù bước transform đã gặp lỗi; trạng thái sai khiến người dùng tin vào dữ liệu chưa hoàn chỉnh.

**Independent Test**: Chạy một lô dữ liệu có kết quả đã biết, sau đó tạo lỗi có kiểm soát tại từng bước bắt buộc và xác nhận trạng thái lượt chạy cùng bước lỗi được báo đúng.

**Acceptance Scenarios**:

1. **Given** một lô hợp lệ có bản ghi cần xử lý, **When** tất cả bước bắt buộc hoàn tất, **Then** báo cáo theo nhãn nguồn số job đã đọc, chuẩn hóa, tạo mới, cập nhật, không đổi và số mapping được thêm/gỡ.
2. **Given** một bước bắt buộc thất bại, **When** lượt chạy kết thúc, **Then** trạng thái được báo là thất bại, tên bước và lỗi được giữ trong kết quả vận hành, và các bước phụ thuộc phía sau không chạy.
3. **Given** đã có dữ liệu được nạp từ lượt trước và một bước bắt buộc thất bại sau khi một phần lô hiện tại đã ghi, **When** lượt chạy dừng, **Then** các ghi dở dang của lô hiện tại được hoàn tác, dữ liệu từ lượt trước vẫn còn và lỗi được báo cho người vận hành.
4. **Given** truy vấn dữ liệu raw cho nhãn nguồn đang cấu hình thành công nhưng có 0 job, **When** lượt chạy kết thúc, **Then** kết quả được ghi rõ là không có dữ liệu thay vì nhầm với lỗi đọc hoặc với một lô đã xử lý.
5. **Given** lô có nhiều nhãn nguồn, **When** lượt chạy xử lý nguồn đang được cấu hình, **Then** chỉ nguồn đó được xử lý và nhãn `WebA` không bị tự đổi tên.
6. **Given** cùng link đã thuộc nhãn nguồn khác, **When** job được xử lý, **Then** lượt chạy báo xung đột, giữ nguyên job cũ và không ghi đè.

---

### User Story 2 - Ánh xạ đúng job mới và job đã thay đổi (Priority: P1)

Người xem phân tích cần job mới được nạp và job đã thay đổi được cập nhật trong dữ liệu chuẩn hóa, với các liên kết kỹ năng, chức danh và cấp bậc phản ánh nội dung hiện tại trước khi lượt chạy kết thúc.

**Why this priority**: Thứ tự hiện tại chạy mapping kỹ năng trước khi nạp job chuẩn hóa; đồng thời job đã tồn tại theo liên kết không nhận thay đổi. Điều này làm báo cáo thiếu job mới, giữ nội dung cũ và để lại mapping sai.

**Independent Test**: Chạy một lô có job mới và một job hiện có với nội dung đã thay đổi; xác nhận bản ghi chuẩn hóa không bị nhân đôi và các liên kết kỹ năng, chức danh, cấp bậc theo đúng dữ liệu mới sau khi lượt chạy thành công.

**Acceptance Scenarios**:

1. **Given** một lô có job mới hợp lệ, **When** lượt chạy thành công, **Then** các job đã nạp được xét ánh xạ kỹ năng, chức danh và cấp bậc trước khi lượt chạy hoàn tất.
2. **Given** job đã có cùng liên kết nguồn nhưng nội dung thay đổi, **When** lượt chạy thành công, **Then** bản ghi chuẩn hóa được cập nhật tại chỗ, không tạo bản sao, và các liên kết kỹ năng, chức danh, cấp bậc phản ánh nội dung hiện tại.
3. **Given** nội dung kỹ năng hoặc cấp bậc của job thay đổi, **When** mapping được tính lại, **Then** liên kết cũ không còn phù hợp được gỡ bỏ và liên kết mới phù hợp được thêm vào.
4. **Given** một job không khớp mục nào trong từ điển hiện tại, **When** lượt chạy thành công, **Then** job vẫn được giữ trong dữ liệu chuẩn hóa và lượt chạy không báo lỗi chỉ vì không có mapping.
5. **Given** dữ liệu nguồn và mapping của job không thay đổi, **When** cùng job được xử lý lại, **Then** không phát sinh job hoặc mapping trùng lặp.
6. **Given** liên kết nguồn đã thuộc một nhãn nguồn khác, **When** job được xử lý, **Then** hệ thống báo xung đột định danh, không ghi đè job cũ và đánh dấu lượt chạy thất bại.

7. **Given** schema phục vụ transform chưa được provision trong database, **When** người vận hành chuẩn bị chạy ETL, **Then** họ có thể áp dụng migration có phiên bản trước; transform không tự tạo hoặc sửa schema trong mỗi lượt.
8. **Given** schema clean đã có dữ liệu từ trước, **When** migration được áp dụng, **Then** các job và mapping hiện có được giữ nguyên và phiên bản migration được ghi nhận.
9. **Given** transform được chạy khi migration bắt buộc chưa được áp dụng, **When** kiểm tra khởi đầu hoàn tất, **Then** tiến trình dừng với hướng dẫn migration rõ ràng và không tự thay đổi cấu trúc database.
10. **Given** job clean có mô tả không rỗng và raw đánh dấu detail chưa hoàn tất với nội dung detail rỗng, **When** job được xử lý lại, **Then** mô tả, kỹ năng, lợi ích đã có được giữ lại và mapping kỹ năng không bị xóa chỉ vì detail chưa hoàn tất.

## Edge Cases

- Lô raw cho nhãn nguồn được cấu hình rỗng sau khi truy vấn database đọc thành công.
- Từ điển kỹ năng hoặc chức danh không đọc được.
- Lỗi xảy ra sau khi một số bước trước đó đã ghi dữ liệu.
- Một job không có kỹ năng hoặc chức danh khớp với từ điển hiện tại.
- Nội dung nguồn của job hiện có đổi khiến mapping trước đó không còn đúng.
- Một lượt chạy lại nhận đúng nội dung cũ và phải giữ nguyên một bản ghi cùng các mapping hiện hành.
- Detail raw chưa hoàn tất có responsibilities, skills hoặc benefits rỗng trong khi clean đã lưu giá trị không rỗng.
- Liên kết job đã tồn tại dưới nhãn nguồn khác; không được gộp hoặc ghi đè dữ liệu đó.
- Một batch gồm nhiều nhãn nguồn; hệ thống chỉ xử lý nguồn hiện đang được cấu hình và không tự đổi nhãn WebA.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST phân biệt lô raw có job để xử lý, lô raw rỗng và lượt thất bại; lỗi truy vấn hoặc đọc dữ liệu MUST NOT được báo như lô rỗng.
- **FR-002**: Hệ thống MUST báo theo từng nhãn nguồn số job đã đọc, chuẩn hóa, tạo mới, cập nhật, không đổi và mapping được thêm/gỡ; nếu lô thất bại, báo cáo MUST nêu các bước hoàn tất và bước lỗi.
- **FR-003**: Hệ thống MUST nạp hoặc cập nhật job chuẩn hóa trước khi xét mapping kỹ năng, chức danh và cấp bậc cho những job đó trong cùng lượt.
- **FR-004**: Hệ thống MUST dừng các bước phụ thuộc sau lỗi ở giai đoạn đọc, nạp từ điển, chuẩn hóa/nạp job hoặc mapping; MUST chuyển lỗi để bộ điều phối đánh dấu tác vụ thất bại.
- **FR-005**: Kết quả thất bại MUST chỉ rõ bước lỗi và thông tin lỗi đã loại bỏ credential/token, đủ để người vận hành tra cứu; ghi log rồi tiếp tục và trả trạng thái thành công là không hợp lệ.
- **FR-006**: Job hợp lệ không có kết quả khớp từ điển MUST vẫn được giữ; trường hợp không khớp không được nhầm với lỗi xử lý.
- **FR-007**: Khi một bước bắt buộc thất bại, hệ thống MUST hoàn tác các ghi dở dang thuộc lô hiện tại nhưng MUST giữ nguyên dữ liệu đã xác nhận từ lượt trước. Lượt đọc thành công nhưng không có dữ liệu MUST NOT xóa dữ liệu đã nạp.
- **FR-008**: Tính năng MUST giữ nguyên nhãn nguồn hiện có; không được suy đoán `WebA` là website cụ thể nếu chưa xác minh.
- **FR-009**: Khi job đã có cùng liên kết và nhãn nguồn nhưng nội dung đổi, hệ thống MUST cập nhật job chuẩn hóa hiện có thay vì tạo bản sao. Nội dung gồm tiêu đề, công ty, lương, địa điểm, loại việc, kinh nghiệm, tags, ngày đăng, logo và chi tiết mô tả đang có trong dữ liệu clean. MUST giữ nguyên khóa liên kết hiện hành; không thêm khóa định danh mới.
- **FR-010**: Khi tiêu đề, kỹ năng hoặc cấp bậc của job thay đổi, hệ thống MUST tính lại mapping chức danh, kỹ năng và cấp bậc theo từ điển hiện hành, thêm liên kết phù hợp và gỡ liên kết cũ không còn phù hợp.
- **FR-011**: Xử lý lại job không đổi MUST NOT tạo job hoặc mapping trùng lặp.
- **FR-012**: Tính năng MUST tiếp tục dùng quy tắc chuẩn hóa và từ điển hiện hành; thay đổi thuật toán matching và chính sách cập nhật dữ liệu raw của crawler là ngoài phạm vi.
- **FR-013**: Nếu cùng liên kết đã thuộc một nhãn nguồn khác, hệ thống MUST báo xung đột và giữ nguyên job hiện có thay vì gộp hoặc ghi đè.
- **FR-014**: Schema clean cần cho transform MUST được provision bằng migration có phiên bản, áp dụng tường minh trước khi chạy ETL. Lượt transform MUST NOT tự thay đổi cấu trúc database; nếu migration cần thiết chưa được ghi nhận, tiến trình MUST dừng với hướng dẫn áp dụng migration. Migration MUST NOT xóa dữ liệu clean hoặc mapping đã tồn tại.
- **FR-015**: Khi raw đánh dấu detail chưa hoàn tất, trường responsibilities, skills hoặc benefits rỗng MUST NOT xóa giá trị không rỗng đã lưu ở jobs_clean; mapping kỹ năng hiện có MUST NOT bị gỡ chỉ vì các trường detail chưa hoàn tất đang rỗng.

### Key Entities

- **Lượt ETL**: Một lần đọc, chuẩn hóa và nạp dữ liệu, có trạng thái, số lượng theo bước và thông tin lỗi khi thất bại.
- **Job nguồn**: Bản ghi đầu vào gắn với nhãn nguồn và liên kết nguồn hiện có.
- **Job chuẩn hóa**: Bản ghi được giữ trong tập dữ liệu dùng cho phân tích sau bước transform.
- **Mapping kỹ năng/chức danh/cấp bậc**: Quan hệ được suy ra từ job chuẩn hóa và từ điển hiện hành.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Với một lô gồm N job nguồn hợp lệ, chưa có trong dữ liệu clean và có liên kết duy nhất, 100% N job được thấy trong dữ liệu chuẩn hóa trước khi lượt chạy thành công kết thúc.
- **SC-002**: Trong mọi tình huống lỗi có kiểm soát ở một bước bắt buộc, 100% lượt chạy được đánh dấu thất bại và không khởi chạy bước phụ thuộc phía sau.
- **SC-003**: Khi truy vấn dữ liệu raw cho nhãn nguồn đang cấu hình thành công nhưng có 0 job, kết quả hiển thị 0 cùng trạng thái không có dữ liệu; đây không phải lỗi đọc hay lô đã xử lý.
- **SC-004**: 100% lượt chạy hoàn tất hoặc thất bại có báo cáo theo nhãn nguồn số liệu đầu vào, chuẩn hóa, job mới/cập nhật/không đổi, mapping thêm/gỡ và bước lỗi nếu có.
- **SC-005**: Với một job đã có cùng liên kết nguồn nhưng thay đổi nội dung, sau một lượt thành công chỉ còn một bản ghi chuẩn hóa và 100% mapping kỹ năng, chức danh, cấp bậc tương ứng phản ánh nội dung mới.
- **SC-006**: Trên database mới, migration provision đầy đủ schema clean cần thiết cho transform; trên database hiện có, số dòng jobs_clean và mapping trước/sau migration không giảm; mỗi lượt transform giữ nguyên cấu trúc database và kiểm tra ledger để xác nhận migration đã áp dụng.
- **SC-007**: Với mọi job có detail trước đó không rỗng và raw đánh dấu detail chưa hoàn tất, sau khi transform các trường detail cũ cùng mapping kỹ năng vẫn còn nguyên.

## Assumptions

- Phạm vi lần đầu là đường transform hiện có; dữ liệu có nhãn WebA vẫn giữ nguyên nhãn cho tới khi website nguồn được xác minh.
- Người dùng kết quả là người vận hành pipeline và người phụ trách dữ liệu phân tích.
- Từ điển kỹ năng và chức danh hiện có là đầu vào chuẩn; tính năng này không thay đổi thuật toán matching.
- Tính năng không mở rộng crawler sang TopCV, VietnamWorks hay LinkedIn, không thêm crawler chi tiết, không đổi API/dashboard, không thay khóa dedup và không thay chính sách cập nhật của bảng raw.
- Khóa liên kết duy nhất đang dùng cho dữ liệu chuẩn hóa tiếp tục là khóa nhận diện job trong phạm vi nguồn hiện cấu hình.
- Migration lần đầu chỉ chuyển việc provision các bảng, index, constraint và hàng seed hiện do transform tạo sang một file SQL có phiên bản; không đổi cấu trúc dữ liệu job hoặc mapping. Bảng schema_migrations chỉ lưu phiên bản migration và thời điểm áp dụng.
- Trường status_crawl_detail hiện có là tín hiệu để không xóa nội dung detail đã lưu khi raw đánh dấu lần tải chưa hoàn tất.
- Schema raw jobs do crawler quản lý không thuộc migration clean của feature này.
- Không có SLA throughput hoặc latency mới trong feature này; phạm vi batch giữ nguyên như hiện tại.
