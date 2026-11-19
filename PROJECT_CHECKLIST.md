# Checklist phần còn thiếu của dự án

Phạm vi: làm cho pipeline TopDev hiện tại đáng tin cậy trước, rồi mới đưa crawler đa nguồn vào vận hành. Checklist được tổng hợp từ [PIPELINE_REVIEW.md](PIPELINE_REVIEW.md), [CRAWLER_PLAN.md](CRAWLER_PLAN.md) và [audit_pipeline.sql](audit_pipeline.sql).

> Trạng thái dữ liệu chưa thể xác nhận ở lần rà soát 2026-10-31: Docker Engine và các cổng database/API/Airflow không truy cập được. Log cũ có lượt transform đọc 0 job nhưng Airflow vẫn báo thành công. Cần chạy lại đối soát trên database đang hoạt động trước khi kết luận dữ liệu đã xử lý hết.

## P0 — Chặn sai lệch dữ liệu và xác nhận hiện trạng

- [ ] **Xác nhận nguồn TopDev thật:** thay `base_url = 'link-demo'`; xác nhận phân trang, trang cuối và URL chi tiết mẫu.
- [ ] **Xác nhận định danh nguồn:** đối chiếu giá trị `WebA` với website thật; không tự đổi dữ liệu cũ nếu chưa xác minh.
- [ ] **Khôi phục môi trường chạy:** kiểm tra Docker Engine, PostgreSQL, Airflow và Flask; xác nhận Airflow có thể gọi crawler trong cấu hình Compose hiện tại.
- [ ] **Đối soát dữ liệu hiện có:** chạy `audit_pipeline.sql`, lưu số raw jobs, clean jobs, detail pending/rỗng, raw chưa clean, mapping thiếu và orphan; đối chiếu mẫu job với nguồn.
- [ ] **Nối crawler chi tiết vào DAG:** chạy sau listing và trước transform; chỉ lấy job pending hoặc đến hạn refresh, có giới hạn batch.
- [ ] **Đặt trạng thái detail rõ ràng:** phân biệt `pending`, `success`, `failed`, `not_found`, `auth_required`; chỉ đánh dấu thành công khi parse hợp lệ.
- [ ] **Không ghi đè nội dung tốt bằng dữ liệu rỗng:** lỗi mạng, trang login, trang chặn hoặc lỗi selector phải giữ dữ liệu tốt đã lưu và được ghi nhận riêng.
- [ ] **Sửa thứ tự ETL:** upsert job và các mapping nền trước, sau đó cập nhật chức danh/kỹ năng; tính lại mapping khi mô tả thay đổi để thêm và xóa kỹ năng cũ.
- [ ] **Làm cho cập nhật lặp an toàn:** thay `DO NOTHING` bằng upsert có điều kiện cho raw/clean; cập nhật chi tiết thay đổi mà không tạo bản sao.
- [ ] **Đảm bảo job và bridge nhất quán:** ghi job, level/skill mapping trong transaction phù hợp; rollback khi bước bắt buộc lỗi.
- [ ] **Để lỗi làm task thất bại:** rollback và raise lỗi SQL/hạ tầng; không chỉ print rồi tiếp tục hoặc báo Airflow `SUCCESS`.
- [ ] **Phân biệt crawl rỗng với nguồn không có tin mới:** xác nhận request/trang crawl thành công và báo cảnh báo nếu không đọc được trang hoặc tổng kết quả bất thường.
- [ ] **Sửa thống kê kỹ năng theo nhóm:** JOIN theo `j.id = fjs.job_id`; đối chiếu kết quả bằng truy vấn đếm trực tiếp.
- [ ] **Sửa matching kỹ năng/chức danh:** hỗ trợ token như `C++`, `C#`; dùng cột alias/keyword, thứ tự ưu tiên rõ ràng và lưu trạng thái đã xử lý kể cả khi không có match.
- [ ] **Ổn định ngày đăng:** ưu tiên timestamp tuyệt đối; với ngày tương đối dùng `fetched_at` có timezone làm mốc để chạy lại không dịch ngày.
- [ ] **Sửa chuẩn hóa địa điểm:** thống nhất cấp tỉnh/thành/quận, hỗ trợ nhiều địa điểm và đồng bộ trường ETL với bộ lọc API.
- [ ] **Sửa hiển thị an toàn:** bỏ nội suy dữ liệu crawl vào `innerHTML`; dùng `textContent`, kiểm tra URL và scheme trước khi dựng liên kết.

## P1 — Hoàn thiện schema, tái lập và vận hành an toàn

- [ ] **Tạo migration riêng:** không chạy DDL ad hoc trong mỗi ETL; bảo đảm FK/constraint được tạo đúng một lần.
- [ ] **Bổ sung định danh và vòng đời job:** lưu `source_job_id`, canonical URL, `first_seen_at`, `last_seen_at`, `fetched_at`, `detail_fetched_at`, `content_hash` và trạng thái mở/đóng phù hợp.
- [ ] **Thêm bảng theo dõi lượt chạy:** lưu run/source, parser/dictionary version, số phát hiện/mới/cập nhật/bỏ qua/lỗi và thời điểm bắt đầu/kết thúc.
- [ ] **Chốt khóa duy nhất:** ưu tiên `(source, source_job_id)`, fallback `(source, canonical_url)`; định nghĩa chuẩn hóa URL mà không bỏ tham số định danh.
- [ ] **Chuẩn hóa quan hệ nhiều-nhiều:** thay `tags_id TEXT[]` bằng bridge có FK; thêm job-location nếu nguồn có nhiều địa điểm.
- [ ] **Giữ dữ liệu lương có nghĩa:** lưu chuỗi gốc và tiền tệ; chỉ điền min/max/period khi parse được, phân biệt unknown/negotiable.
- [ ] **Rà soát ràng buộc dữ liệu:** validate URL/title trước khi load; thêm NOT NULL/CHECK sau khi xử lý bản ghi cũ; lưu lý do cho rejected records.
- [ ] **Dọn schema dư và constraint trùng:** quyết định vai trò `company_mapping.location_id`; kiểm tra FK chức danh và các ràng buộc hiện có.
- [ ] **Đưa CSV mapping vào bản triển khai tái lập:** xử lý `.gitignore`, version hóa từ điển và ghi hash/version trong mỗi lượt ETL.
- [ ] **Đóng tài nguyên DB đúng cách:** đảm bảo cursor/connection được đóng cả khi lỗi trong crawler chi tiết và các bước ETL.
- [ ] **Quản lý dữ liệu bền vững:** cấu hình named volume cho PostgreSQL, quy trình backup và thử restore.
- [ ] **Bảo vệ cấu hình:** đưa credential khỏi source code, không ghi cookie/token vào log, dùng role DB tối thiểu và tắt Flask debug ngoài môi trường phát triển.
- [ ] **Pin dependency:** khóa phiên bản Scrapy, curl_cffi, Airflow và thư viện liên quan; xác nhận tương thích trong image triển khai.

## P1 — Sửa transport và lỗi API

- [ ] **Sửa đường truyền crawler:** middleware `curl_cffi.get()` hiện gọi mạng đồng bộ và bỏ qua một phần request/response semantics của Scrapy; chuyển sang downloader handler/middleware tương thích hoặc PoC transport mới.
- [ ] **Giữ status/header/final URL và retry đúng:** phân biệt HTTP lỗi, redirect login, 403/429, lỗi mạng và lỗi parse; không biến mọi tình huống thành một loại lỗi chung.
- [ ] **Chỉ bật HTTP cache sau khi đường truyền hỗ trợ cache hit:** hiện middleware trả response trước `HttpCacheMiddleware`; xác nhận thứ tự, cache key, TTL và loại trừ trang login/lỗi.
- [ ] **Sửa truy vấn API nặng:** phân trang danh sách job trước, sau đó aggregate skill/level; tránh JOIN tạo tích dòng trước COUNT.
- [ ] **Ổn định phân trang:** thêm khóa phụ `j.id` vào sắp xếp; trả HTTP 400 khi page không hợp lệ.
- [ ] **Cải thiện frontend fetch:** kiểm tra `response.ok`, hiển thị lỗi API và bỏ qua response cũ bằng AbortController hoặc request sequence.

## P2 — Mở rộng crawler đa nguồn

- [ ] **Khảo sát từng nguồn trước khi viết adapter:** lưu URL mẫu, trường dữ liệu, cách phân trang, transport cần dùng, trạng thái đăng nhập và giới hạn request cho TopCV, VietnamWorks và nguồn khác.
- [ ] **Làm PoC Crawlee có giới hạn:** so sánh với transport Scrapy đã sửa trên cùng URL bằng độ đầy đủ dữ liệu, tốc độ, RAM và khả năng resume; quyết định migration theo số đo.
- [ ] **Tạo hợp đồng dữ liệu chung và adapter riêng:** mỗi nguồn tự xử lý selector, auth, rate limit, retry và chuẩn hóa đặc thù; ETL không phụ thuộc HTML từng site.
- [ ] **Triển khai phiên đăng nhập khi nguồn cần:** login helper cục bộ để người dùng hoàn thành OTP/CAPTCHA; lưu session state ngoài Git và filesystem có quyền hạn; khôi phục được sau restart.
- [ ] **Bắt lỗi hết phiên:** nhận diện redirect/login HTTP 200/401; lưu tiến độ, đánh dấu `AUTH_REQUIRED` và tiếp tục sau khi người dùng xác thực lại.
- [ ] **Tuân thủ tốc độ riêng từng nguồn:** concurrency/delay/backoff theo domain và tài khoản; khi gặp 429 thì giảm tốc và chờ theo phản hồi nguồn.
- [ ] **Lưu mẫu parser an toàn:** giữ HTML/JSON đã loại credential để so sánh parser khi website đổi; đặt thời hạn lưu.
- [ ] **Thêm TopCV và VietnamWorks lần lượt:** mỗi nguồn xuất cùng schema, chạy độc lập và có thống kê riêng trước khi mở lịch chung.
- [ ] **Chốt cách tiếp cận LinkedIn trước connector:** xác minh feed/API/provider được cấp quyền hoặc dùng trang tuyển dụng gốc; chưa cam kết tiến độ crawler khi chưa rõ đường truy cập.
- [ ] **Giữ tin đăng trùng liên nguồn có truy vết:** lưu record theo nguồn riêng; chỉ nhóm job tương đương bằng logic dedup riêng sau khi có dữ liệu thực.

## P2 — Điều phối, cache và tiêu chí phát hành

- [ ] **Hoàn thiện Airflow:** lịch chạy, retry backoff đúng phiên bản, thông báo lỗi thật và một nhánh độc lập cho mỗi nguồn.
- [ ] **Bỏ phụ thuộc tên container cố định:** tham số hóa lệnh chạy crawler và xác nhận Docker CLI/quyền truy cập trong runtime Airflow.
- [ ] **Ghi metrics theo run/source:** request thành công/lỗi, job mới/cập nhật, độ đầy đủ trường, auth expiry, 403/429, lỗi parse, thời gian và số detail đang retry.
- [ ] **Cache ETL theo batch:** preload dimension ID, compile regex một lần mỗi run và nạp lại khi version từ điển đổi.
- [ ] **Chỉ thêm cache API sau khi đo:** bắt đầu với `/api/filters` TTL ngắn; invalidate sau publish thành công. Chỉ thêm Redis nếu latency/DB metrics cho thấy cần.
- [ ] **Đo query trước khi thêm index:** dùng EXPLAIN và workload thực tế; ưu tiên bridge/FK/filter có truy vấn chiều ngược nhiều.
- [ ] **Chạy kiểm chứng theo nguồn:** parser mẫu, auth còn/hết phiên, lỗi 429, restart/resume queue, upsert, ETL mapping và API; đối chiếu thủ công mẫu job với trang gốc.
- [ ] **Chạy end-to-end có kiểm soát:** 20–50 job mỗi nguồn khi đủ dữ liệu; so sánh số liệu giữa crawler hiện tại và adapter mới qua nhiều lượt.
- [ ] **Viết hướng dẫn vận hành/rollback:** cách chạy thủ công, xác thực lại, xem run lỗi, resume, backup/restore và quay lại crawler cũ.

## Điều kiện coi là hoàn tất

- [ ] Một lượt crawl thành công được phân biệt rõ với lượt rỗng, lỗi trang, lỗi auth hoặc parse thất bại.
- [ ] Job mới, cập nhật và mapping xuất hiện nhất quán sau một lượt ETL; chạy lại không tạo bản sao.
- [ ] Detail pending/lỗi có thể retry/resume; dữ liệu hợp lệ không bị ghi đè bởi response rỗng.
- [ ] Báo cáo run cho thấy độ phủ và lỗi theo từng nguồn; có thể đối soát raw → clean → API.
- [ ] TopDev ổn định trước khi mở rộng; sau đó ít nhất TopCV và VietnamWorks dùng cùng hợp đồng dữ liệu.
- [ ] Ít nhất một nguồn cần đăng nhập có thể khôi phục session sau restart mà không để lộ credential.
- [ ] LinkedIn chỉ được đánh dấu hoàn thành khi đã xác định được phương thức truy cập phù hợp và được phép.
