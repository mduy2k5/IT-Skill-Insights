---
description: "Dependency-ordered task list for the IT job platform"
---

# Tasks: Nền tảng việc làm IT

**Input**: Design documents from `/specs/002-it-job-platform/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Spec không yêu cầu TDD hoặc task automated test. Mỗi story có tiêu chí kiểm chứng độc lập; các kịch bản fixture/thủ công nằm trong [quickstart.md](quickstart.md).

**Organization**: Tasks được nhóm theo bốn user stories và thứ tự ưu tiên trong spec.

## Format: `- [ ] [TaskID] [P?] [Story?] Description`

- **[P]**: Có thể làm song song vì sửa file khác và không phụ thuộc task chưa hoàn thành.
- **[Story]**: Nhãn user story tương ứng, chỉ có trong các phase user story.
- Mỗi task nêu file cụ thể để sửa hoặc tạo.

## Phase 1: Setup

**Purpose**: Chuẩn bị cấu hình và dữ liệu fixture dùng chung.

- [ ] T001 [P] Tạo `.env.example` chỉ chứa tên biến cấu hình `SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` và ngưỡng quota, không chứa credential thật.
- [ ] T002 [P] Cập nhật `.gitignore` để loại trừ `.env`, credential cục bộ, log crawl và output/artifact tạm.
- [ ] T003 [P] Tạo `data/fixtures/README.md` quy định fixture phải synthetic hoặc có quyền sử dụng, không chứa HTML/JD sao chép từ nguồn chưa được duyệt.

---

## Phase 2: Foundational

**Purpose**: Hạ tầng schema, model, quyền nguồn và trạng thái chung bắt buộc trước khi xây từng story.

- [ ] T004 Tạo migration runner trong `scraper/job_crawler/migration_runner.py` để bootstrap tracking table khi chạy lệnh migrate, áp dụng file SQL có version theo thứ tự, ghi mỗi version một lần vào `schema_migrations`, và báo lỗi rõ khi migration thất bại.
- [ ] T005 [P] Tạo `scraper/job_crawler/migrations/002_job_platform_core.sql` cho `job_sources`, `crawl_windows`, `crawl_runs`, `jobs`, `job_descriptions`; đưa schema raw `jobs` hiện có vào migration hoặc chuyển đổi tương thích không mất dữ liệu; dùng trạng thái nguồn `pending_review`, `approved`, `blocked`, `revoked`, trạng thái window `pending`, `running`, `complete`, `empty`, `paused`, `failed`, `listing_status` gồm `active`, `expired`, `removed`, `unknown`, unique `(source_id, requested_from, requested_to)` và `(source_id, source_job_key)`.
- [ ] T006 Refactor `scraper/job_crawler/transform/database.py`, `scraper/job_crawler/run_transform.py` và `scraper/job_crawler/pipelines.py` để không chạy DDL trong `ensure_tables()`, mỗi lượt transform hoặc `open_spider()`; chỉ kiểm tra schema version và hướng dẫn chạy migration runner khi thiếu migration.
- [ ] T007 Cập nhật `scraper/job_crawler/transform/database.py` để đọc kết nối từ environment, không ghi URL/credential vào log, và dùng kết nối runtime không có quyền quản trị schema.
- [ ] T008 [P] Chuẩn hóa item/domain fields trong `scraper/job_crawler/items.py` theo data model: source identity bắt buộc; dữ liệu cơ bản thiếu để null/unknown; `listing_status` gồm `active`, `expired`, `removed`, `unknown`; `detail_status` gồm `not_requested`, `pending`, `complete`, `empty`, `unavailable`, `not_authorized`.
- [ ] T009 [P] Tạo hợp đồng Scrapy spider/item và registry trong `scraper/job_crawler/sources/base.py` và `scraper/job_crawler/sources/registry.py`; adapter mặc định tắt nếu quyền nguồn chưa `approved` hoặc thiếu flag sử dụng phù hợp.
- [ ] T010 [P] Tạo bộ quản lý trạng thái/log run trong `scraper/job_crawler/orchestration/run_tracker.py` để phân biệt kết quả rỗng hợp lệ, lỗi request, authentication, parse, detail và DB; lưu số liệu theo source/window/stage.
- [ ] T011 [P] Tạo quota guard trong `scraper/job_crawler/storage/quota_guard.py`: cảnh báo từ 70% DB quota và chặn ingest mới từ 80%; khi chặn không được thử dịch vụ trả phí.

**Checkpoint**: Migration tường minh, model chung, source permission gate và run/quota guard sẵn sàng.

---

## Phase 3: User Story 1 — Thu thập dữ liệu lịch sử theo từng giai đoạn (Priority: P1)

**Goal**: Người vận hành chọn nguồn/cửa sổ lịch sử, theo dõi kết quả và tiếp tục sau gián đoạn mà không tạo job trùng.

**Independent Test**: Dùng fixture cho ít nhất ba cửa sổ; dừng sau một cửa sổ rồi resume; xác nhận source/window/count/cursor, không trùng khóa tự nhiên, `empty` khác lỗi; TopDev `pending_review` phải tạo 0 request mạng.

- [ ] T012 [P] [US1] Tạo hồ sơ quyền nguồn tại `specs/002-it-job-platform/source-onboarding/topdev.md`, ghi URL do người dùng cung cấp, đường dẫn và ngày kiểm tra điều khoản/robots (đánh dấu chưa xác minh nếu chưa có bằng chứng), flags crawl/lưu/phân tích/hiển thị riêng và mặc định `pending_review`.
- [ ] T013 [P] [US1] Tạo fixture synthetic tối thiểu tại `data/fixtures/topdev_jobs.json` gồm job có đủ trường, job thiếu trường và trạng thái mô tả khác nhau; không sao chép nội dung từ TopDev.
- [ ] T014 [P] [US1] Tạo bộ chia khoảng thời gian trong `scraper/job_crawler/orchestration/window_planner.py` hỗ trợ khoảng do operator chọn và cắt thành năm/tháng/window nhỏ với cận ngày rõ ràng.
- [ ] T015 [P] [US1] Tạo Scrapy Selector/parser listing TopDev trong `scraper/job_crawler/sources/topdev/listing.py` để map fixture/source payload sang item chung, giữ `source_job_key`, canonical URL và trường thiếu dạng null.
- [ ] T016 [P] [US1] Tạo Scrapy Selector/parser chi tiết trong `scraper/job_crawler/sources/topdev/detail.py` để map mô tả và trạng thái `complete`, `empty`, `unavailable`, `not_authorized`; lỗi/rỗng không ghi đè mô tả hợp lệ đã lưu.
- [ ] T017 [US1] Tạo writer/checkpoint trong `scraper/job_crawler/orchestration/ingest.py` dùng unique key `(source_id, source_job_key)`, upsert idempotent, cập nhật cursor/bộ đếm tích lũy và giữ raw source label/URL.
- [ ] T018 [US1] Tạo Scrapy Spider request/pagination trong `scraper/job_crawler/sources/topdev/spider.py` và `scraper/job_crawler/sources/topdev/config.py`; chỉ bật network khi `permission_status=approved` và quyền cần thiết được xác nhận; cấu hình tối đa 1 request/domain, delay ít nhất 3 giây, AutoThrottle, kiểm tra robots và pause ở 403/429/login/chặn, không vượt bảo vệ.
- [ ] T019 [US1] Tạo operator CLI trong `scraper/job_crawler/cli.py` để gọi Scrapy runner/spider với `--source`, `--from`, `--to`, `--dry-run`, `--resume`; chạy migration riêng với ingest và trả exit code lỗi khi đầu ra bắt buộc thất bại.
- [ ] T020 [US1] Tạo `.github/workflows/job-ingestion.yml` để gọi Scrapy CLI với source/window qua `workflow_dispatch` và lịch incremental mỗi Chủ nhật 03:17 UTC; khóa concurrency theo source, lấy secrets an toàn, checkpoint vào DB và không dùng Actions artifacts/cache làm trạng thái bền vững.

**Checkpoint**: Có thể xử lý fixture theo window, resume/idempotent; live TopDev chỉ hoạt động sau khi hoàn thành cổng quyền.

---

## Phase 4: User Story 2 — Tìm và xem job IT, ưu tiên Data (Priority: P1)

**Goal**: Người tìm việc duyệt/tìm/lọc job Data, mở chi tiết, và thấy rõ tình trạng mô tả/coverage.

**Independent Test**: Nạp fixture vào DB; tìm/lọc `project_track=data` theo địa điểm, nhãn seniority nguyên gốc từ nguồn và ngày; mọi kết quả mở được chi tiết; mô tả không được phép hiển thị phải null với availability phù hợp; anonymous chỉ đọc public views/RPC.

- [ ] T021 [P] [US2] Tạo `scraper/job_crawler/migrations/003_public_catalog.sql` cho `public_jobs`, `public_job_details`, `public_source_coverage` và RPC `search_public_jobs`; lọc theo quyền hiển thị nguồn, không expose raw tables, query tối đa 120 ký tự, `page >= 1`, `per_page` từ 1 đến 50 mặc định 12, và cấp quyền public chỉ đọc.
- [ ] T022 [US2] Tạo client Supabase public API trong `web/public/assets/js/api.js`, dùng duy nhất `SUPABASE_URL` và publishable key; gọi đúng resource/RPC trong `contracts/job-catalog.openapi.yaml`, xử lý lỗi/rate limit và không chứa secret.
- [ ] T023 [P] [US2] Tạo trang danh sách/tìm kiếm trong `web/public/index.html`, `web/public/assets/js/jobs.js` và `web/public/assets/css/site.css`; hỗ trợ query, `project_track=data`, địa điểm, lọc nhãn seniority nguyên gốc, ngày đăng, pagination và trạng thái mô tả.
- [ ] T024 [P] [US2] Tạo trang chi tiết trong `web/public/job.html` và `web/public/assets/js/job-detail.js`; hiển thị trường cơ bản, source URL và trạng thái mô tả, chỉ render JD khi `display_description=true`.
- [ ] T025 [P] [US2] Tạo phần coverage trong `web/public/coverage.html` và `web/public/assets/js/coverage.js`; chỉ hiển thị nguồn được phép công khai cùng trạng thái `complete`, `empty`, `partial` hoặc `unavailable` theo window, không lộ lỗi nội bộ; truy vấn `limit` từ 1 đến 100 mặc định 50.
- [ ] T026 [P] [US2] Cấu hình Cloudflare Pages output `web/public/` và hướng dẫn deploy trong `docs/deployment/cloudflare-pages.md`; không thêm backend/secret vào static bundle.
- [ ] T027 [P] [US2] Đồng bộ schema, tham số, giới hạn và response của `contracts/job-catalog.openapi.yaml` với SQL view/RPC và các trang web; giữ public read contract tách khỏi ingestion credentials.
- [X] T049 [US2] Tận dụng Flask hiện có làm trang preview cục bộ đọc các bảng OLTP bằng role PostgreSQL chỉ đọc; hỗ trợ danh sách, tìm/lọc/phân trang và chi tiết job; bind cổng host vào loopback, không bật quyền hiển thị công khai.
- [X] T050 [US1] Thêm bước verify artifact trước khi nạp: kiểm tra khóa trùng, trường bắt buộc, URL, timestamp, lương, mô tả, công ty, địa điểm, work mode và listing status; chỉ cho ghi OLTP khi operator truyền `--apply` và không có lỗi.
- [X] T051 [US1] Thêm migration `database/postgres/004_job_ingest_candidates.sql` và luồng `--verify` tách riêng trong `scraper/job_crawler/job_validation.py`, được gọi từ `scraper/job_crawler/load_crawl_artifacts.py`; lưu nguyên JSON từng job cùng lỗi/cảnh báo/trạng thái, chỉ nạp candidate `verified` còn pending, không cấp quyền đọc staging cho role website, cập nhật data model và quickstart.
- [X] T052 [US3] Thêm container `job-olap` dùng DuckDB Quack, named volume riêng, token bắt buộc, port chỉ bind loopback, migration schema star warehouse và hướng dẫn migrate/khởi động trong `database/olap/` cùng quickstart; location tùy chọn/nhiều địa điểm phải qua bridge.

**Checkpoint**: Website static phục vụ tìm kiếm, lọc, chi tiết, coverage qua API chỉ đọc.

---

## Phase 5: User Story 3 — Xem nhu cầu kỹ năng theo trình độ (Priority: P2)

**Goal**: Tính kỹ năng cần thiết từ mô tả được phép phân tích; nhóm theo seniority/khoảng ngày, giữ mẫu số và bằng chứng.

**Independent Test**: Dùng fixture mô tả synthetic với seniority đã biết và chưa rõ; đối chiếu số job đã phân tích, nhóm unknown, kỹ năng/bằng chứng và thống kê theo thời gian với các bản ghi được lưu.

- [X] T028 [P] [US3] Tạo schema DuckDB trong `database/olap/migrations/001_warehouse_core.sql` với taxonomy có version, phân tích kỹ năng, evidence và mart trong `warehouse`; không thêm taxonomy hoặc join bắt buộc vào đường ingest/đọc job OLTP. Replay key là `(job_key, analyzer_key, description_hash)`.
- [ ] T029 [P] [US3] Tạo `data/skill_taxonomy.csv` gồm `canonical_name`, `category`, `taxonomy_version`, `active` cùng alias tiếng Việt/Anh; bảo đảm `normalized_alias` không xung đột trong cùng version/language sau khi xử lý trùng.
- [ ] T030 [P] [US3] Tạo `data/seniority_mapping.csv` ánh xạ nhãn level theo source sang nhóm chung, giữ nguyên raw label và ánh xạ không biết thành `unknown`.
- [ ] T031 [US3] Tạo extractor baseline trong `scraper/job_crawler/analysis/skill_extractor.py` chuẩn hóa text, match alias theo biên từ phù hợp và lưu offset/trích đoạn, confidence, `match_method`, analyzer/taxonomy version.
- [ ] T032 [US3] Tạo batch analyzer trong `scraper/job_crawler/analysis/run_skill_analysis.py` chỉ xử lý mô tả có quyền `analyze_description=true`; không gửi JD tới hosted AI API; ghi kết quả vào DuckDB `warehouse.fact_job_analysis`, `fact_job_skill`, `fact_job_skill_evidence` theo replay key và không thay analysis cũ khi mô tả/taxonomy thay đổi.
- [ ] T033 [US3] Tạo `database/postgres/005_skill_statistics_api.sql` với RPC công khai có quyền tối thiểu trên bảng aggregate nhỏ được đồng bộ từ `warehouse.mart_skill_demand_monthly`; yêu cầu `period_start`/`period_end`, hỗ trợ `limit` từ 1 đến 100 mặc định 30 theo posted date/source/`project_track`/seniority; trả `analyzed_job_count`, `unclassified_job_count`, nhóm `unknown`, số job từng skill và bằng chứng chỉ khi được phép hiển thị. Không cho website truy vấn trực tiếp DuckDB.
- [ ] T034 [US3] Tạo trang kỹ năng tại `web/public/skills.html` và `web/public/assets/js/skills.js`; hiển thị seniority, thời gian, mẫu số, phần chưa phân loại và evidence excerpt không quá 280 ký tự.
- [ ] T035 [P] [US3] Tạo ví dụ synthetic cho phân tích tại `data/fixtures/skill_examples.json` gồm alias đa ngôn ngữ, từ không phải kỹ năng, level không biết và expected evidence để operator đối chiếu thủ công.
- [ ] T036 [US3] Đánh giá model local `intfloat/multilingual-e5-small` trên mẫu synthetic/được phép và ghi accuracy, RAM, thời gian, kích thước tải cùng điều kiện chạy $0 vào `specs/002-it-job-platform/ai-evaluation.md`; chỉ đề xuất tích hợp nếu tiếng Việt cải thiện baseline và chạy được bằng tài nguyên miễn phí/cục bộ.

**Checkpoint**: Thống kê chỉ tính analysis hoàn tất/được phép, truy nguyên được từng kỹ năng và trình bày mẫu số theo nhóm.

---

## Phase 6: User Story 4 — Mở rộng sang nhiều website độc lập (Priority: P2)

**Goal**: Onboard nguồn kế tiếp theo adapter riêng; lỗi/giới hạn một nguồn không chặn nguồn khác.

**Independent Test**: Chạy hai fixture source trong cùng lượt; cho một nguồn trả lỗi có kiểm soát; nguồn kia vẫn hoàn tất với run/count riêng; kiểm tra adapter web thật vẫn tắt nếu chưa được phê duyệt.

- [ ] T037 [US4] Tạo checklist onboarding nguồn tại `specs/002-it-job-platform/source-onboarding/README.md` gồm URL hiện hành, điều khoản, robots, quyền thu thập/lưu/phân tích/hiển thị, rate policy, định danh job, parser fixture và ngày review.
- [ ] T038 [P] [US4] Kiểm tra URL/điều khoản/robots và khả năng truy cập TopCV; ghi nguồn tham chiếu, flags quyền riêng và trạng thái tại `specs/002-it-job-platform/source-onboarding/topcv.md`; giữ adapter disabled nếu chưa xác nhận.
- [ ] T039 [P] [US4] Kiểm tra URL/điều khoản/robots và khả năng truy cập VietnamWorks; ghi nguồn tham chiếu, flags quyền riêng và trạng thái tại `specs/002-it-job-platform/source-onboarding/vietnamworks.md`; giữ adapter disabled nếu chưa xác nhận.
- [ ] T040 [P] [US4] Tạo Scrapy Spider/adapter TopCV tại `scraper/job_crawler/sources/topcv/` theo contract chung, parse fixture trước; mọi live request phải qua `permission_status=approved`, throttle riêng và stop policy.
- [ ] T041 [P] [US4] Tạo Scrapy Spider/adapter VietnamWorks tại `scraper/job_crawler/sources/vietnamworks/` theo contract chung, parse fixture trước; mọi live request phải qua `permission_status=approved`, throttle riêng và stop policy.
- [ ] T042 [US4] Tạo multi-source runner trong `scraper/job_crawler/orchestration/source_runner.py` để ghi status/error/count riêng theo source, tiếp tục các source còn lại khi một source thất bại và serialize theo domain.
- [ ] T043 [P] [US4] Tạo fixture adapter thành công/thất bại trong `scraper/job_crawler/sources/fixture_ok.py` và `scraper/job_crawler/sources/fixture_fail.py` để kiểm chứng độc lập mà không truy cập website thật.
- [ ] T044 [US4] Tích hợp registry, CLI và GitHub Actions trong `scraper/job_crawler/sources/registry.py`, `scraper/job_crawler/cli.py` và `.github/workflows/job-ingestion.yml` để chọn source/window riêng, không làm lỗi một adapter hủy các source khác.

**Checkpoint**: Nguồn bổ sung được đăng ký riêng, có review/quota policy riêng; kiểm chứng cô lập lỗi bằng fixture trước khi bật live adapter.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Vận hành trong quota miễn phí, bảo vệ dữ liệu/credential và giữ hướng dẫn khớp implementation.

- [ ] T045 Tạo runbook quota/backup tại `docs/operations/free-tier-runbook.md` ghi hạn mức Supabase/GitHub Actions/Pages, ngưỡng 70%/80%, thao tác dump/restore và cách resume sau pause.
- [ ] T046 Cập nhật `README.md` về kiến trúc platform, môi trường local, source permission gates, adapter flow, giới hạn free-tier và phạm vi website.
- [ ] T047 Cập nhật `specs/002-it-job-platform/quickstart.md` với lệnh CLI/workflow thực tế sau khi triển khai; giữ các kịch bản resume, quyền pending, quota guard, website/API, skills và source isolation.
- [ ] T048 Thêm redaction cho credential/header/cookie và dữ liệu nhạy cảm trong `scraper/job_crawler/logging_config.py`; run summary chỉ ghi error stage/code, không ghi secret hoặc toàn bộ response nguồn.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Không phụ thuộc phase khác.
- **Foundational (Phase 2)**: Bắt đầu sau Setup; bắt buộc hoàn thành trước các user stories.
- **US1 (Phase 3)**: Cần core schema, migration runner, source contract và quota/run controls.
- **US2 (Phase 4)**: Cần core job schema; có thể dựng/kiểm chứng bằng fixture độc lập với live crawl của US1.
- **US3 (Phase 5)**: Cần job/description schema và quyền analyze; có thể xây bằng fixture, production stats phụ thuộc dữ liệu được phép từ US1.
- **US4 (Phase 6)**: Dùng adapter contract từ Foundation và checkpoint/runner của US1; TopCV/VietnamWorks live execution còn phụ thuộc từng hồ sơ quyền nguồn.
- **Polish (Phase 7)**: Sau các stories được chọn để phát hành.

### User Story Dependencies

- **US1 (P1)**: Sau Phase 2; độc lập với US2/US3 khi kiểm chứng bằng fixture. TopDev live crawl bị chặn cho tới khi hồ sơ quyền được duyệt.
- **US2 (P1)**: Sau Phase 2; độc lập với US1 nếu dùng dữ liệu synthetic, nhưng public catalog thực tế cần job được phép hiển thị.
- **US3 (P2)**: Sau Phase 2; có thể phát triển cùng US1/US2 bằng fixture, nhưng phân tích production cần mô tả được phép analyze và hiển thị kết quả.
- **US4 (P2)**: Sau adapter foundation; source runner cần cơ chế run/checkpoint của US1. Adapter TopCV/VietnamWorks có thể parse fixture khi chưa được quyền, không được gửi live requests.

### Parallel Opportunities

- **Setup**: T001, T002, T003 sửa các file độc lập.
- **Foundation**: T008–T011 nằm ở module riêng; có thể làm sau khi model/migration interfaces thống nhất.
- **US1**: T012–T016 là hồ sơ quyền, fixture, planner và parser ở file khác nhau; T015 và T016 cũng độc lập sau khi item contract ổn định.
- **US2**: T021, T026, T027 có thể chuẩn bị riêng; sau T022, T023–T025 là các bề mặt UI riêng.
- **US3**: T028–T030 và T035 có thể làm song song; T031, T032, T033, T034 cần theo thứ tự extractor → batch → aggregation/API → UI; T036 là đánh giá bổ sung sau baseline và fixture.
- **US4**: T038/T039 là review hồ sơ nguồn độc lập; T040/T041 và T043 là module/fixture riêng; T042/T044 ghép nối sau các interfaces.
- **Stories**: US1/US2 và phần fixture của US3 có thể triển khai song song sau Foundation; US4 cần adapter contract ổn định.

## Parallel Example: User Story 1

```text
Song song sau Foundation:
T012 TopDev source-onboarding record
T013 synthetic TopDev fixture
T014 time-window planner
T015 listing parser
T016 detail parser

Sau đó theo thứ tự:
T017 idempotent writer/checkpoint → T018 gated source spider → T019 CLI → T020 workflow
```

## Parallel Example: User Story 2

```text
T021 public API migration, T026 Pages config, T027 OpenAPI alignment có thể chuẩn bị song song.
Sau T022 API client, làm T023 listing UI, T024 detail UI và T025 coverage UI song song.
```

## Parallel Example: User Story 3

```text
Song song: T028 schema migration, T029 skill taxonomy, T030 seniority mapping, T035 synthetic skill examples.
Theo thứ tự: T031 extractor → T032 batch analyzer → T033 statistics RPC → T034 analytics UI.
Sau T031/T035, T036 đánh giá embedding local có thể chạy riêng; không chặn MVP dictionary baseline.
```

## Parallel Example: User Story 4

```text
Song song: T038 TopCV review và T039 VietnamWorks review.
Sau adapter contract: T040 TopCV fixture adapter, T041 VietnamWorks fixture adapter và T043 failure fixtures.
Sau đó ghép T042 source runner → T044 registry/CLI/workflow.
```

## Implementation Strategy

### MVP First

1. Hoàn thành Setup và Foundation, nhất là migration runner và loại DDL khỏi transform path.
2. Làm US1 bằng fixture, chứng minh cửa sổ/resume/idempotency/quota; chỉ bật TopDev live sau khi rights gate được giải quyết.
3. Làm US2 để có sản phẩm người dùng thấy được. Vì vậy **MVP kỹ thuật** là US1; **MVP website công khai** tối thiểu cần US1 + US2 và một source có quyền hiển thị.
4. Dừng ở từng checkpoint; không chuyển sang US3/US4 trước khi luồng dữ liệu tương ứng có fixture hoặc source được phép.

### Incremental Delivery

1. Setup + Foundation → schema/version và adapter contracts.
2. US1 → backfill slices an toàn, status và resume.
3. US2 → catalog tĩnh và public read API.
4. US3 → skill demand analytics sau khi có mô tả được phép xử lý.
5. US4 → onboard mỗi nguồn riêng, chỉ bật sau khi xác minh quyền và throttle.

## Notes

- Không có task automated test riêng vì spec không yêu cầu TDD; các Independent Test criteria và quickstart vẫn cần được dùng khi người dùng yêu cầu verification/implementation.
- TopDev/TopCV/VietnamWorks hồ sơ chưa được duyệt không cho phép live request; parser fixture có thể phát triển độc lập.
- Các nguồn Vietlamtot và Xomdata là ứng viên cho vòng onboarding sau; chưa có task live adapter vì URL/permission chưa được xác minh.
- Supabase schema migration phải chạy tường minh trước ingest; không cấp quyền DDL cho worker.
- Dừng usage trước quota miễn phí, không tự chuyển sang plan trả phí.
