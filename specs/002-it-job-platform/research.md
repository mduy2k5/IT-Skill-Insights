# Research: Nền tảng việc làm IT

Ngày cập nhật quyết định Scrapy: 2026-11-09. Các quota dịch vụ đã được khảo sát ngày 2026-11-04; cần đối chiếu lại khi bật tài khoản và cấu hình quota.

## 1. TopDev: quyền nội dung và độ ổn định nguồn

**Decision**: Ghi TopDev là nguồn ưu tiên theo lựa chọn của người dùng, nhưng khởi tạo ở trạng thái `pending_review`. Không phát request crawl, lưu nội dung hoặc công khai mô tả cho tới khi quyền thu thập, lưu trữ, phân tích và hiển thị được xác nhận bằng điều khoản/API được phép hoặc chấp thuận phù hợp. Xác minh lại URL, robots, giới hạn truy cập và định danh nguồn ngay trước khi triển khai adapter.

**Rationale**: Điều khoản TopDev hiện công bố quyền sở hữu trí tuệ với nội dung website và hạn chế sao chép, truyền, phân phối, công bố, hiển thị hoặc khai thác nội dung. Đây là cổng cần xử lý trước khi cung cấp dữ liệu trên nền tảng công khai; việc URL mở được không chứng minh quyền sử dụng. Trang chủ hiện còn thông báo TopDev sẽ hợp nhất vào Saramin Vietnam từ giữa tháng 11/2026, nên tên miền/URL và nguồn dữ liệu có thể đổi ngay trong giai đoạn phát triển. Ghi ngày xác minh và lưu bằng chứng điều khoản/permission của từng nguồn.

**Alternatives considered**:
- Tiến hành crawl vì trang job đang truy cập công khai: không chọn; không giải quyết quyền sao chép và tái hiển thị.
- Dùng feed/API hoặc văn bản cấp phép do nguồn cung cấp: ưu tiên nếu có và phạm vi cho phép đủ dữ liệu lịch sử/mô tả.
- Khi chưa được chấp thuận: giữ TopDev tắt, kiểm thử bằng fixture hoặc đưa một nguồn khác vào MVP sau khi xác minh quyền riêng.

Nguồn: [Điều khoản sử dụng TopDev](https://topdev.vn/term-of-services), [thông báo trên trang chủ TopDev](https://topdev.vn/).

## 2. Crawler và mô hình adapter

**Decision**: Dùng Python 3.10 và Scrapy cho crawler hiện tại cùng tất cả adapter mới; không triển khai Crawlee runtime song song. Tạo hợp đồng Scrapy spider/item chung nhưng cho phép parser, pagination, giới hạn, trạng thái listing/detail và quyền của mỗi nguồn cấu hình độc lập. Giữ mặc định không quá một request đồng thời/domain, độ trễ tối thiểu 3 giây theo cấu hình hiện có và AutoThrottle; tăng chậm hơn khi nguồn yêu cầu. 403, 429, login wall, captcha hoặc dấu hiệu chặn chuyển run sang paused/blocked và không thử vượt bảo vệ.

**Rationale**: Repo đã có Scrapy spider, pipeline và cài đặt giới hạn per-domain (`CONCURRENT_REQUESTS_PER_DOMAIN=1`, `DOWNLOAD_DELAY=3`, AutoThrottle). Dùng Scrapy xuyên suốt giữ một runtime, một Item Pipeline và một bộ quy tắc vận hành trong khi tách parser theo nguồn. User đã chọn rõ Scrapy; không tạo nhánh triển khai Crawlee. Code adapter mới không phụ thuộc Cloudscraper hay biện pháp giả lập/vượt kiểm soát truy cập.

**Alternatives considered**:
- Dùng Crawlee cho nguồn mới còn Scrapy cho nguồn cũ: không chọn theo quyết định hiện tại của người dùng; chỉ xem lại framework qua spec mới và bằng chứng đo được nếu có nhu cầu mới.
- Giữ nguyên một spider tổng hợp cho nhiều domain: không chọn vì parser và lỗi của một nguồn sẽ khó cô lập.
- Bật lại crawler hiện hữu nguyên trạng: không chọn; setting hiện tại tắt kiểm tra robots và code có Cloudscraper middleware, cần đánh giá quyền/robots và an toàn trước khi dùng adapter mới.

## 3. Chạy tự động bằng GitHub Actions

**Decision**: Dùng workflow có `workflow_dispatch` cho backfill do người vận hành yêu cầu và lịch thưa cho incremental check khi cần. Mỗi run xử lý một cửa sổ nhỏ, ghi checkpoint/run result vào PostgreSQL; khóa concurrency theo source để không có nhiều worker cùng crawl một domain. Lưu cấu hình và secrets trong repository/environment secrets; không lưu checkpoint trong cache/artifact. Không dùng artifact để giữ nội dung job.

**Rationale**: Standard hosted runner miễn phí với repository công khai; repository private có allowance theo gói, GitHub Free hiện ghi 2.000 phút/tháng và 500 MB artifact storage. Usage vượt allowance có thể tính phí khi cấu hình thanh toán cho phép. Lịch `schedule` có thể trễ/bị bỏ lúc tải cao, chạy trên default branch và repository công khai có thể tự tắt schedule sau 60 ngày không hoạt động; do đó workflow không phải queue hay scheduler có SLA. Để giữ ngân sách $0, không dùng runner lớn, cấu hình budget dừng chi tiêu hoặc tắt thanh toán overage, và theo dõi usage trước backfill dài.

**Alternatives considered**:
- GHA schedule như hàng đợi bền vững: không chọn vì event có thể trễ hoặc mất; trạng thái phải ở DB.
- Luôn bật Airflow/Docker trên máy chủ: không chọn cho hosted MVP vì cần một máy chạy liên tục; vẫn giữ Compose/Airflow để phát triển và chạy cục bộ.
- Public repo để mọi Actions minute miễn phí: không giả định; repo hiện tại chưa xác nhận visibility và không được mở công khai chỉ để lấy quota.

Nguồn: [GitHub Actions schedule](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [GitHub Actions usage](https://docs.github.com/en/actions/concepts/billing-and-usage), [quota theo gói](https://docs.github.com/en/billing/reference/product-usage-included), [concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

## 4. PostgreSQL và Supabase Free

**Decision**: Dùng Supabase Free làm nơi chạy thử cho schema PostgreSQL và Data API, nhưng coi đó là quota-limited MVP, không phải kho lưu trữ vô hạn. Bật RLS và chỉ cấp quyền đọc cho các view/RPC công khai; không đưa secret/service credential vào browser. Tạo cảnh báo khi DB đạt 70% quota và dừng import mới trước 80%; có quy trình dump dữ liệu ra nơi người vận hành kiểm soát. Nếu quota không đủ cho mô tả lịch sử, thu hẹp cửa sổ/chờ hoặc xin thay đổi ngân sách/spec; không tự động chuyển sang trả phí.

**Rationale**: Supabase Free hiện công bố 500 MB database/project, 1 GB file storage, 5 GB egress và 5 GB cached egress; project có thể pause sau 7 ngày hoạt động thấp. Free không có automatic backups. Nội dung mô tả dài có thể làm cạn quota nhanh, nên không đưa ảnh vào storage, không lưu bản HTML thô trừ khi quyền và nhu cầu đã xác nhận, đo dung lượng thực tế mỗi batch, và duy trì bản dump có thể khôi phục. Supabase Data API tạo REST API từ schema; grants/RLS phải giới hạn các bảng được truy cập.

**Alternatives considered**:
- Supabase Free như nơi lưu toàn bộ mọi tin/job vĩnh viễn: không chọn vì giới hạn dung lượng và pause khiến điều này không bền.
- Managed DB trả phí: ngoài ràng buộc $0 của MVP; chỉ xem lại khi người dùng chủ động thay ngân sách/spec.
- PostgreSQL local-only: giữ được chi phí $0 nhưng không đáp ứng website công khai và API hosted.

Nguồn: [Supabase pricing](https://supabase.com/pricing), [billing limits](https://supabase.com/docs/guides/platform/billing-on-supabase), [free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing), [backups](https://supabase.com/docs/guides/platform/backups), [Data REST API](https://supabase.com/docs/guides/api), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security).

## 5. Website và public API

**Decision**: Phục vụ HTML/CSS/JS tĩnh trên Cloudflare Pages Free; client gọi Supabase Data API qua public views/RPC chỉ đọc. Giữ API contract ổn định ở mức tài nguyên nghiệp vụ (`public_jobs`, chi tiết job, thống kê kỹ năng và coverage), không lộ raw tables. Website phân trang và chỉ hiện mô tả khi source permission cho phép.

**Rationale**: Cloudflare Pages Free hiện giới hạn 500 builds/tháng, một build đồng thời, 20.000 files/site và 25 MiB/file; đủ cho website tĩnh ở quy mô MVP. Supabase Data API cho phép browser đọc qua REST, nhưng browser key chỉ an toàn khi quyền table/view/RLS được cấu hình đúng. Gọi thẳng Data API tránh cần một server Flask luôn chạy; Flask hiện hữu tiếp tục phục vụ local trong thời gian chuyển đổi. Nếu mai sau cần logic API riêng, đánh giá Pages Functions/Workers Free (hiện 100.000 requests/ngày, 10 ms CPU/request) nhưng không cần cho MVP hiện tại.

**Alternatives considered**:
- Flask API trên host free chưa được xác nhận: không chốt vì chưa khảo sát độ bền/lifecycle của host, và thêm dịch vụ cần duy trì.
- Pages Functions cho mọi endpoint ngay: không chọn vì SQL views/RPC và RLS đủ cho interface đọc cơ bản; thêm runtime chưa cần thiết.
- GitHub Pages: không chọn ở bước này vì yêu cầu công khai repository trên gói Free và có hạn chế sử dụng như hosting SaaS; Pages của Cloudflare khớp hơn với mục tiêu web tĩnh.

Nguồn: [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/), [Pages Git integration](https://developers.cloudflare.com/pages/configuration/git-integration/), [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/).

## 6. Phân tích kỹ năng và AI với ngân sách $0

**Decision**: Bản đầu dùng taxonomy kỹ năng có alias tiếng Việt/Anh và matching chuẩn hóa, lưu trích đoạn hoặc offset chứng minh kỹ năng trong JD, phiên bản taxonomy và số job được phân tích. Đây là baseline dễ rà soát và chạy trong pipeline Python hiện tại. Đánh giá semantic matching cục bộ bằng `intfloat/multilingual-e5-small` như bước mở rộng chỉ sau khi có tập mẫu gán nhãn tiếng Việt và xác nhận chạy trong tài nguyên miễn phí/cục bộ; không phụ thuộc hosted inference API hoặc LLM có thể phát sinh phí.

**Rationale**: Kết quả thống kê cần truy nguyên và đối chiếu được. Từ điển có bằng chứng giúp tạo baseline đo được, đồng thời tránh upload JD lên dịch vụ AI bên ngoài. Embedding đa ngôn ngữ có thể bổ sung cách viết biến thể nhưng model có giới hạn 512 token và hiệu quả với tiếng Việt phải được đo trên dữ liệu dự án. Inference providers phổ biến không đảm bảo quota miễn phí cố định; riêng Hugging Face free user không có inference credits đi kèm.

**Alternatives considered**:
- Gọi Gemini/Hugging Face hosted free tier cho mọi mô tả: không chọn vì quota/điều khoản có thể thay đổi, dữ liệu rời khỏi hệ thống và có rủi ro tiêu phí.
- Coi keyword matching là kết quả AI hoàn chỉnh: không chọn; đánh dấu nó là baseline NLP, mở rộng semantic khi có phép đo và tập đánh giá.
- Local embedding ngay trong mọi GitHub run: chưa chọn cho MVP vì runner/giới hạn phút, model download và bộ nhớ chưa được đo.

Nguồn: [model card multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), [Hugging Face inference pricing](https://huggingface.co/docs/inference-providers/en/pricing), [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing).

Tài liệu Scrapy chính thức cho các setting và khả năng pause/resume: [settings](https://docs.scrapy.org/en/latest/topics/settings.html), [AutoThrottle](https://docs.scrapy.org/en/latest/topics/autothrottle.html), [jobs](https://docs.scrapy.org/en/latest/topics/jobs.html).

## 7. Migration và trạng thái schema hiện tại

**Decision**: Mọi schema thay đổi của feature 002 phải có file SQL migration có version, chạy tường minh và ghi nhận một lần. Chuyển phần DDL đang được gọi mỗi lượt transform ra khỏi `ensure_tables()`/transform path; transform chỉ xác nhận schema cần thiết và xử lý dữ liệu. Trước khi áp dụng migration, kiểm kê bảng dữ liệu hiện có, backup, và kiểm tra migration đã áp dụng để tránh mất dữ liệu.

**Rationale**: Hiến pháp cấm DDL chạy mỗi ETL run. Repo đã có `scraper/job_crawler/migrations/001_transform_schema.sql` và bảng `schema_migrations`, nhưng `transform/database.py`/run path cần được hội tụ để entrypoint không khởi tạo schema mỗi lần. Migration rõ ràng giúp môi trường local và hosted có cùng phiên bản schema, audit được thay đổi và giảm race.

**Alternatives considered**:
- Giữ DDL lặp lại vì có `IF NOT EXISTS`: không chọn; vẫn là schema mutation trong data run và che lỗi deploy.
- Chạy migration tự động trong từng worker trước crawl: không chọn; có thể cạnh tranh khi workers đồng thời và quyền schema không nên nằm trong crawler role.
- Alembic ngay lập tức: chưa chọn; migration SQL đã tồn tại và PostgreSQL-specific; đánh giá lại khi schema rollout cần tooling/lifecycle phức tạp hơn.

## Open decisions / điều kiện phải xác nhận trước khi thực thi

1. Quyền của TopDev hoặc feed/API thay thế, gồm lịch sử, nội dung JD, lưu trữ cho phân tích và tái hiển thị.
2. TopDev/Saramin URL, robots, phạm vi dữ liệu lịch sử và phương thức truy cập sau thay đổi thương hiệu.
3. Visibility GitHub repo và budget cap của tài khoản; không công khai repo theo suy đoán.
4. Khả năng kết nối Supabase project, RLS/API keys và ngân sách dung lượng cho tập dữ liệu mẫu; chưa tạo project từ plan này.
5. Danh sách nguồn mở rộng: URL và điều khoản của TopCV, VietnamWorks, Vietlamtot, Xomdata chưa được xác minh.
