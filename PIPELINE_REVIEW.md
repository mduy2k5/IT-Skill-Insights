# Rà soát pipeline TopDev

Ngày rà soát: 2026-10-31. Phạm vi là phiên bản hiện tại chỉ crawl TopDev; `WebA`/`weba` là tên nguồn đang được dùng trong code.

## Kết luận

Pipeline có đủ các thành phần cơ bản, nhưng chưa bảo đảm dữ liệu đi đầy đủ và chính xác từ crawl tới dashboard. Ưu tiên sửa luồng chi tiết, cơ chế cập nhật, mapping và báo lỗi trước khi thay framework hoặc thêm nguồn.

- Chưa thể xác nhận số lượng bản ghi thiếu trong database hiện tại: Docker Engine không truy cập được và localhost:5433, 5000, 8088 đều đóng lúc kiểm tra.
- Log lưu từ 2026-05-22 cho thấy các lượt transform đọc **0 jobs** rồi Airflow vẫn báo **SUCCESS**. Đây là bằng chứng của những lượt chạy cũ, không phải số liệu DB hôm nay.
- Code hiện tại có đường đi làm thiếu dữ liệu ngay cả khi task thành công: bỏ crawl detail, skill mapping chạy sớm, lỗi bị nuốt và dữ liệu cũ không được cập nhật.
- Schema raw/clean + dimension/bridge là nền tảng hợp lý; cần hoàn thiện nhận diện job, vòng đời dữ liệu, quan hệ địa điểm/tag và transaction.
- Nên bổ sung cache có mục đích; cơ chế xử lý tăng dần và trạng thái bền vững trong DB quan trọng hơn thêm Redis vào thời điểm này.

## 1. Các lỗi ảnh hưởng trực tiếp đến dữ liệu

### F01 — P1: DAG bỏ qua bước lấy chi tiết

**Bằng chứng:** `dags/job_pipeline.py:34–44`; `pipelines.py:96–98` khởi tạo responsibilities/skills/benefits bằng chuỗi rỗng.

DAG chỉ chạy danh sách rồi transform. Nếu chưa chạy detail thủ công, dữ liệu clean nhận mô tả rỗng và không có đầu vào để trích xuất kỹ năng.

**Chỉnh:** thêm task detail trước transform, kiểm tra tỷ lệ detail hoàn tất và tách trường hợp nguồn thực sự không có nội dung khỏi lỗi parse.

### F02 — P1: Skill mapping chạy trước khi có job mới

**Bằng chứng:** `run_transform.py:94–99`.

Job mới chỉ được thêm sau khi skill mapping chạy, nên thiếu mapping trong lượt đầu. Nếu clean đã được tạo với skills rỗng thì chạy lại cũng không tự khắc phục do F03.

**Chỉnh:** nạp từ điển → upsert jobs và level/tag/location → mapping chức danh → mapping kỹ năng → kiểm tra chất lượng.

### F03 — P1: Dữ liệu cũ không được cập nhật hoặc sửa đầy đủ

**Bằng chứng:** `pipelines.py:83`; `transform/database.py:385`, `391–415`; skill transform dòng 34.

- Raw danh sách và clean đều dùng `ON CONFLICT (link) DO NOTHING`.
- Detail cập nhật vào raw nhưng clean đã tồn tại không nhận mô tả mới.
- Level bridge chỉ được ghi khi INSERT job thành công. Nếu job đã commit nhưng bridge lỗi, lần chạy sau bỏ qua job nên không sửa được bridge.
- Skill transform loại mọi job đã có ít nhất một mapping; không nhận kỹ năng mới khi mô tả/từ điển thay đổi, không xóa mapping cũ.

**Chỉnh:** upsert có kiểm soát, content hash và version quy tắc; tính lại mapping của job thay đổi trong transaction. Không ghi đè mô tả tốt bằng dữ liệu rỗng từ request/parse lỗi.

### F04 — P1: Báo thành công khi dữ liệu rỗng hoặc SQL lỗi

**Bằng chứng:** `run_transform.py:13–53`, `73–77`, `98–104`; `pipelines.py:55–65`; `database.py:394`, `412–425`.

Lỗi SQL thường bị in ra rồi tiếp tục mà không rollback/re-raise đúng phạm vi. Kết nối PostgreSQL sau một statement lỗi có thể ở trạng thái aborted, làm các bước tiếp theo cùng thất bại. Job và bridge được commit rời nhau nên dữ liệu có thể dở dang. Pipeline không kết nối DB cũng có thể trả item mà không lưu.

**Chỉnh:** lỗi hạ tầng phải làm task thất bại; transaction nguyên tử cho một job/batch và bridge; rollback/savepoint rõ ràng; đối soát số input/accepted/rejected. Một lượt không có tin mới là hợp lệ nếu nguồn được đọc thành công; crawl 0 trang hoặc mất toàn bộ dữ liệu cần cảnh báo riêng.

**Log:** `logs/dag_id=job_pipeline/run_id=manual__2026-05-22T144323.055890+0000/task_id=transform_jobs/attempt=2.log:18–26` có 0 jobs và SUCCESS.

### F05 — P1: Thống kê kỹ năng theo nhóm nối sai khóa

**Bằng chứng:** `web/app.py:224`.

`j.job_title_mapping_id = fjs.job_id` ghép ID chức danh với ID job. Có thể sinh số liệu trông hợp lệ nhưng thuộc job khác.

**Chỉnh:** nối `j.id = fjs.job_id`; đối chiếu một nhóm nhỏ với truy vấn đếm trực tiếp sau khi sửa mapping dữ liệu.

### F06 — P1: Regex kỹ năng và từ điển chức danh chưa được dùng đúng

**Bằng chứng:** `job_skill_requirement_transform.py:46`; `job_title_transform.py:15–21`; `database.py:441–461`.

- Đã tái hiện pattern hiện tại không nhận `C++` trong `Experience with C++ and SQL`, không nhận `C#` trong `C# developer`. Cả hai tồn tại trong CSV.
- CSV kỹ năng có 180 dòng. Cần token boundary phù hợp dấu `+`, `#`, `.`, alias và kiểm tra ngữ cảnh để tránh nhận nhầm tên ngắn.
- CSV chức danh có 169 dòng, 79 standard titles. Cột `keyword` bị bỏ qua, nên alias có trong từ điển như `data eng` không được map sang Data Engineer.
- Một tiêu đề có nhiều tên chuẩn phù hợp sẽ được UPDATE nhiều lần; SELECT từ điển không ORDER BY và không có quy tắc ưu tiên, nên lựa chọn cuối không có thứ tự được bảo đảm.

**Chỉnh:** bảng alias → title/skill chuẩn, priority/specificity rõ ràng, version từ điển; lưu trạng thái đã xử lý dù không có match. Tỷ lệ không có match không đồng nghĩa tất cả đều lỗi.

### F07 — P1: Ngày đăng và địa điểm có thể sai

**Bằng chứng:** `weba_transformer.py:33–51`, `54–83`; `web/app.py:21–25`.

- Ngày tương đối dùng `datetime.now()`: cùng `3 days ago` xử lý ngày 31/10 cho 28/10, xử lý lại ngày 07/11 thành 04/11.
- Mẫu ngày tuyệt đối `2026-05-20` trả NaT. Mẫu `today` hoặc `a day ago` gây ValueError; đây là kiểm tra khả năng xử lý bằng input mẫu, chưa xác nhận nguồn hiện trả các chuỗi này.
- Mẫu địa điểm đơn `Ho Chi Minh` được ghi vào city, province rỗng. API danh sách bộ lọc chỉ lấy province, khiến địa điểm đó không có trong dropdown.
- Tách địa điểm theo vị trí dấu phẩy không đủ phân biệt quận/thành phố/tỉnh hoặc nhiều văn phòng.

**Chỉnh:** ưu tiên ngày tuyệt đối/timestamp từ nguồn; lưu `fetched_at` có múi giờ làm mốc cho ngày tương đối. Chuẩn hóa địa danh bằng từ điển và xử lý nhiều địa điểm; đồng bộ trường được lọc giữa ETL và API. Ngày lịch sử thiếu mốc không được tự suy ra thành ngày chính xác.

### F08 — P2: Phạm vi crawl và trạng thái detail chưa đầy đủ

**Bằng chứng:** `spiders/it_jobs.py:9–10`; `spiders/it_jobs_detail.py:22`; `pipelines.py:67–77`.

- Checkout đang dùng URL mẫu và chỉ 4 trang cố định. Cần URL thật và cơ chế đi tới trang cuối/mốc thời gian, có giới hạn an toàn.
- Detail đọc toàn bộ jobs, không lọc `status_crawl_detail`; DB connection/cursor đọc link chưa được đóng rõ ràng.
- Detail rỗng vẫn được gắn cờ thành công. Không phân biệt trang login, tin hết hạn, trang bị chặn và lỗi selector.

**Chỉnh:** trạng thái `pending/success/failed/not_found/auth_required`, attempt count, thời gian thử lại và thời gian refresh. Dùng DB quyết định job nào cần tải lại, kèm kiểm tra nội dung và giới hạn batch.

### F09 — P1: Dữ liệu crawl được chèn trực tiếp vào HTML

**Bằng chứng:** `web/static/js/main.js:121–155`.

Tên công ty, tiêu đề, lương và URL từ nguồn được nội suy vào `innerHTML` mà chưa escape. Nội dung có HTML hoặc dấu nháy có thể trở thành markup/script trong trình duyệt.

**Chỉnh:** dựng DOM bằng `textContent`, thiết lập thuộc tính an toàn và kiểm tra scheme URL; nếu dùng template string thì escape đúng text/attribute context.

## 2. Database: phần tốt và phần cần chỉnh

**Phần tốt:** raw tách clean; unique URL chống trùng cơ bản; mapping company/location/date; bridge job–level và job–skill có khóa kép; các truy vấn tìm kiếm chính dùng tham số SQL.

| Vấn đề | Chỉnh tối thiểu cho TopDev |
|---|---|
| Thiếu grain/định danh nguồn bền vững | Lưu ID job từ TopDev nếu có và canonical URL; thống nhất tên nguồn. Dùng ID/URL làm khóa upsert theo chính sách rõ ràng |
| Không biết độ mới hay tin đã đóng | Thêm first_seen_at, last_seen_at, detail_fetched_at, transformed_at, content_hash, trạng thái job và thời điểm kiểm tra lại. Chỉ đánh dấu biến mất sau lượt crawl đủ phạm vi |
| Không đo được hoàn tất ETL | Thêm crawl/etl run records: đầu vào, mới, cập nhật, lỗi, bỏ qua, chưa xử lý; hash/version parser và từ điển |
| tags_id là TEXT[] chứa ID | Dùng bridge job–tag với FK như job–skill; tránh ID trong mảng không kiểm tra được FK từng phần tử |
| Mỗi job chỉ có một location_id | Dùng job–location nếu nguồn có nhiều địa điểm; thống nhất cấp tỉnh/thành/quận thay vì suy ra bằng vị trí chuỗi |
| Lương và kinh nghiệm chỉ có TEXT; clean còn xóa chữ USD ở `weba_transformer.py:7` | Giữ raw và đơn vị; thêm min/max/currency/period và experience_min/max khi parse được; dùng trạng thái unknown/negotiable rõ ràng |
| Company/cấp bậc chủ yếu lowercase + strip | Phân biệt tên raw, alias và canonical; cần quy tắc rõ cho các biến thể tên/cấp bậc trước khi gộp thống kê |
| Link/title nullable hoặc chuỗi rỗng vẫn được chấp nhận | Validate trước load, CHECK/NOT NULL phù hợp sau khi dọn dữ liệu; rejected records có lý do |
| company_mapping.location_id TEXT chưa được dùng | Bỏ trường dư hoặc định nghĩa quan hệ đúng sau khi xác định ý nghĩa nghiệp vụ |
| DDL chạy trong mỗi ETL | Migration riêng; `database.py:139` thêm FK chức danh mỗi lần mà không kiểm tra tồn tại, có thể tạo constraint dư |
| Thiếu index phục vụ truy vấn chiều ngược | Đo EXPLAIN trước khi thêm; ứng viên gồm bridge `(skill_id, job_id)`, `(level_id, job_id)`, các FK lọc nhiều, title mapping và ngày đăng |
| Airflow và dữ liệu job cùng DB/role | Tách schema/DB và quyền ứng dụng để migration metadata và thao tác dữ liệu job dễ kiểm soát |
| PostgreSQL chưa có named/bind volume trong Compose | Cấu hình volume ổn định và backup/restore; không suy ra rằng restart đơn thuần sẽ mất dữ liệu, nhưng anonymous volume khó quản lý qua thay container |

Không cần chuyển database sang sản phẩm khác để giải quyết các vấn đề này. PostgreSQL đáp ứng mô hình hiện tại; chưa có số đo để kết luận cần partition, Elasticsearch hay Redis.

Phân phối ngày đăng hiện là đếm các job đã lưu theo ngày đăng, chưa phải lịch sử thị trường đầy đủ. Muốn phân tích số job đang mở theo từng ngày cần dữ liệu vòng đời/snapshot và độ phủ crawl theo thời gian.

## 3. Cache: nên có ở đâu?

| Lớp | Đề xuất | Cách hết hạn/cập nhật |
|---|---|---|
| ID dimension trong ETL | Cache dictionary theo batch/run; preload hoặc bulk join thay cho SELECT từng company/location/tag/level/date của mỗi job | Cập nhật khi thêm dimension; cache có giới hạn bộ nhớ |
| Regex và từ điển | Compile một lần mỗi run; tách alias khỏi canonical | Nạp lại khi version/hash CSV thay đổi |
| HTML/JSON nguồn | Snapshot có giới hạn để debug và chạy lại parser; HTTP cache tùy nhu cầu refresh | Theo TTL/freshness mục tiêu; không coi lỗi/login/CAPTCHA là dữ liệu job thành công |
| Tiến độ crawl | Lưu DB và hàng đợi/JOBDIR để tiếp tục sau lỗi | Đây là trạng thái bền vững, không phải cache có thể xóa tùy tiện |
| Detail đã tải | Dùng fetched_at/hash/trạng thái để quyết định refresh | Tin mới/lỗi ưu tiên; tin đang mở có chu kỳ kiểm tra lại |
| `/api/filters` | Có thể cache ngắn hạn, ví dụ 10–30 phút | Invalidate sau khi publish ETL thành công |
| Analytics | Có thể cache 1–5 phút hoặc theo data_version | Invalidate khi dữ liệu phục vụ báo cáo được commit/publish |
| Tìm kiếm/phân trang | Đo sau khi sửa query/index; nếu cache thì giới hạn số khóa và gồm toàn bộ filter/page/data_version | TTL ngắn; tránh cache vô hạn theo từ khóa người dùng |

Các TTL trên là gợi ý vận hành, chưa phải kết quả đo tải.

**Điểm cần xử lý trước khi bật HTTP cache:** middleware curl_cffi ở priority 100 trả Response trước khi HttpCacheMiddleware mặc định ở 900 nhận `process_request`. Vì vậy chỉ bật `HTTPCACHE_ENABLED` không tạo được cache hit trước request mạng trên đường hiện tại. Nên tích hợp downloader/handler đúng cơ chế Scrapy hoặc đặt lớp cache ở trước transport với key và policy rõ ràng.

Middleware hiện còn gọi mạng đồng bộ, bỏ qua request method/body/headers/proxy của Scrapy, chuyển lỗi thành IgnoreRequest và trả HtmlResponse thiếu status/header/final URL gốc. Điều này làm retry, cache, cookie và số liệu download không phản ánh đầy đủ giao dịch thực. Sửa transport trước khi tăng concurrency hoặc đánh giá crawler chậm/nhanh.

## 4. API, điều phối và vận hành

- `api_jobs` JOIN level và skill cùng lúc tạo tích các dòng; DISTINCT giúp kết quả không trùng nhưng tăng công tổng hợp. COUNT không cần JOIN tất cả dữ liệu hiển thị. Nên chọn page job ID trước rồi aggregate level/skill cho page đó.
- Thêm khóa phụ `j.id` vào ORDER BY để phân trang ổn định khi nhiều job cùng ngày; validate `page` không phải số để trả 400.
- Frontend chưa kiểm tra `response.ok`; lỗi API có thể bị hiểu thành không có job/skill. Request tìm kiếm cũ có thể hoàn tất sau request mới; dùng AbortController hoặc request sequence.
- `schedule_interval=None` nghĩa là chưa có lịch tự chạy. Failure callback chỉ print, chưa gửi thông báo. Cấu hình backoff dùng tên `exponential_backoff` thay vì `retry_exponential_backoff` của Airflow 2.9.
- Lệnh `docker exec` phụ thuộc tên container cố định. Mount docker.sock chưa bảo đảm có Docker CLI/quyền truy cập trong image Airflow; cần xác nhận ở runtime.
- Dependency chưa pin phiên bản nên build lại có thể thay hành vi spider/pipeline; kiểm tra tương thích API Scrapy của bản thực tế trước khi chốt image.
- Hai CSV mapping bị gitignore. Clean checkout thiếu chúng sẽ không tái lập được ETL đầy đủ.
- Các dịch vụ dùng credential hardcode; ứng dụng Flask chạy debug=True. Đưa cấu hình ra môi trường, tắt debug khi triển khai ngoài máy phát triển và dùng role DB phù hợp.
- PBIX có model nhị phân và một trang report trong archive. Chưa xác minh được relationship/DAX, chế độ Import/DirectQuery hoặc độ mới của dữ liệu bên trong. Cần mở trong Power BI và refresh/đối soát sau khi DB hoạt động; ảnh dashboard không chứng minh dữ liệu hiện tại đã đầy đủ.

## 5. Kiểm tra đã thực hiện

- Đọc toàn bộ mã crawl, middleware, pipeline lưu raw, transform, schema, mapping, DAG, Compose, API và JavaScript phục vụ dữ liệu.
- Kiểm tra cú pháp bằng AST cho 17 file Python tracked: parse thành công. Đây không phải kiểm tra import/dependency/runtime.
- Tách và chạy nguyên hàm/pattern từ AST với input mẫu và clock kiểm soát; dùng stub tối thiểu cho pandas. Xác nhận lỗi boundary C++/C#, alias không match, ngày tương đối dịch theo thời điểm và locality một thành phần không vào province.
- Đọc CSV thật: 180 dòng skill, 169 dòng title/79 standard titles.
- Đọc log lịch sử và cấu trúc archive PBIX; không thay đổi model.
- Kiểm tra kết nối runtime: Docker Engine không truy cập được; các cổng ứng dụng/database hiện đóng. Không chạy crawl lên TopDev trong lượt audit và không ghi vào DB.

## 6. Đối soát dữ liệu khi database hoạt động

File `audit_pipeline.sql` đi kèm là các truy vấn chỉ đọc cho schema hiện tại. Script mở transaction READ ONLY và cần các bảng đã được khởi tạo.

Cần lấy ít nhất các chỉ số sau trước khi kết luận “đã xử lý hết”:

1. Tổng raw, pending detail và detail được báo thành công nhưng nội dung rỗng.
2. Raw chưa có clean; raw có detail mới nhưng clean chưa đồng bộ.
3. Clean thiếu chức danh/cấp bậc/ngày/địa điểm; job có text kỹ năng nhưng chưa có mapping.
4. Orphan FK/ID tag, constraint trùng và các index đang tồn tại.
5. Đối chiếu mẫu với trang gốc, bao gồm job đang mở, đã gỡ và mô tả thay đổi.

Các tỷ lệ null/unmapped là tín hiệu để phân loại nguyên nhân, không mặc định tất cả đều là lỗi. Script không thể xác nhận độ phủ toàn bộ TopDev nếu không có thông tin trang cuối/tổng kết quả/mốc crawl từ nguồn.

## 7. Thứ tự chỉnh đề xuất

1. **Độ đúng:** bổ sung detail vào DAG, skill mapping sau upsert, sửa JOIN analytics, dùng alias và token boundary đúng.
2. **Khả năng sửa dữ liệu cũ:** upsert, transaction job–bridge, fail-fast, trạng thái xử lý và đối soát.
3. **Ý nghĩa dữ liệu:** ngày có mốc thu thập, địa điểm chuẩn hóa, lương giữ tiền tệ, trường không xác định có trạng thái rõ.
4. **Độ bền:** volume/backup, migrations, dependency pin, quy trình khôi phục và dữ liệu CSV tham chiếu.
5. **Hiệu năng:** batch DB, cache mapping/regex, query/index và cache API dựa trên số đo.
6. **Mở rộng:** đánh giá lại việc chuyển Crawlee và bổ sung nguồn sau khi luồng TopDev có số liệu kiểm chứng.

## Tài liệu xác minh hành vi thư viện

- [Scrapy: thứ tự downloader middleware và Response trả sớm](https://docs.scrapy.org/en/latest/topics/downloader-middleware.html)
- [Scrapy: priority mặc định của HTTP cache](https://docs.scrapy.org/en/latest/topics/settings.html#downloader-middlewares-base)
- [Airflow 2.9: retry_exponential_backoff](https://airflow.apache.org/docs/apache-airflow/2.9.0/_api/airflow/models/baseoperator/index.html)
- [Docker Compose: named volumes](https://docs.docker.com/reference/compose-file/volumes/)
