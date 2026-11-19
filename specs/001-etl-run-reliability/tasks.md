# Tasks: Độ tin cậy của lượt ETL

**Input**: Design documents from /specs/001-etl-run-reliability/

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Không tạo task automated tests; feature không yêu cầu TDD và repository hiện không có test suite. Tiêu chí kiểm chứng độc lập và lệnh áp dụng migration nằm trong specs/001-etl-run-reliability/quickstart.md.

**Organization**: Tasks grouped by user story. Migration provisioning and shared connection ownership are foundational prerequisites for both P1 stories.

## Format: [ID] [P?] [Story] Description

- [P]: Task can be worked in parallel after its dependencies finish.
- [Story]: User story served by the task.
- Each task names its exact implementation file.

## Phase 1: Setup

**Purpose**: Use the current Python, Docker, Airflow, and PostgreSQL environment.

Không cần package hoặc runtime dependency mới.

---

## Phase 2: Foundational

**Purpose**: Provision clean schema explicitly and establish runner-owned database access.

- [x] T001 Create a transactional, versioned migration with the existing clean tables, indexes, constraints, and seed rows plus a schema_migrations ledger in scraper/job_crawler/migrations/001_transform_schema.sql; preserve existing jobs and mapping rows.
- [x] T002 Remove ensure_tables and its DDL implementation after transferring the clean-schema objects to scraper/job_crawler/migrations/001_transform_schema.sql in scraper/job_crawler/transform/database.py.
- [x] T003 [P] Replace the ensure_tables call with a read-only migration-version preflight that fails with application instructions in scraper/job_crawler/run_transform.py.
- [x] T004 Refactor transform write helpers to use the runner-owned connection and return counts without committing or closing it in scraper/job_crawler/transform/database.py.
- [x] T005 [P] Make the skill helper use the supplied shared connection and return mapping-change counts in scraper/job_crawler/job_skill_requirement_transform.py.
- [x] T006 [P] Make the title helper use the supplied shared connection and return mapping-change counts in scraper/job_crawler/job_title_transform.py.

**Checkpoint**: A versioned clean-schema migration is available, the ETL has no runtime schema DDL, and write helpers can share the batch connection.

---

## Phase 3: User Story 1 - Tin cậy trạng thái lượt chạy (Priority: P1) MVP

**Goal**: Report succeeded, no_data, or failed with source and stage details; rollback the current batch on failure and let Airflow observe it.

**Independent Test**: Follow the migration preflight, successful batch, empty-source, controlled-failure, and rollback scenarios in specs/001-etl-run-reliability/quickstart.md. Confirm migration is required before writes, no_data returns 99, failures propagate, summaries identify the failing stage, and batch rollback retains prior data.

### Implementation for User Story 1

- [x] T007 Track required stages and report per-source input, normalized, inserted, updated, unchanged, and mapping added/removed counts in scraper/job_crawler/run_transform.py.
- [x] T008 Wrap batch writes in one transaction in scraper/job_crawler/run_transform.py; commit only after required stages succeed, rollback on exceptions, include the failing stage and sanitized error, then re-raise.
- [x] T009 Return no_data with exit code 99 only after a successful raw read yields no configured-source jobs in scraper/job_crawler/run_transform.py.
- [x] T010 Configure the transform BashOperator to treat exit code 99 as skipped in dags/job_pipeline.py.

**Checkpoint**: The migration preflight, success, empty batch, and failure paths have explicit outcomes; failed writes roll back.

---

## Phase 4: User Story 2 - Ánh xạ đúng job mới và job đã thay đổi (Priority: P1)

**Goal**: Upsert normalized jobs by the existing link, then synchronize title, skill, and level mappings to current content without duplicates or cross-source overwrites.

**Independent Test**: Follow the new-job, changed-job, unchanged-rerun, unmatched-dictionary, and cross-source conflict scenarios in specs/001-etl-run-reliability/quickstart.md. Compare clean rows and mappings before and after each run.

### Implementation for User Story 2

- [x] T011 Upsert all existing clean job fields by link and configured source, preserve non-empty detail when status_crawl_detail is false, count inserted/updated/unchanged rows, and raise a source-identity conflict without overwriting another source in scraper/job_crawler/transform/database.py.
- [x] T012 Recompute title mappings for newly inserted or changed jobs and clear stale title mappings when the current title no longer matches in scraper/job_crawler/job_title_transform.py.
- [x] T013 Reconcile skill mappings for newly inserted, changed, and previously unmapped jobs; add current matches and remove stale matches in scraper/job_crawler/job_skill_requirement_transform.py.
- [x] T014 Reconcile job-level mappings for newly inserted or changed jobs and remove stale level mappings in scraper/job_crawler/transform/database.py.
- [x] T015 Run clean-job upsert before title, skill, and level mapping stages and aggregate their change counts in scraper/job_crawler/run_transform.py.

**Checkpoint**: New and changed jobs have current mappings; unchanged reprocessing creates no duplicate job or mapping.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Keep operator instructions aligned with migration and ETL behavior.

- [x] T016 Document the explicit migration command, ledger check, migration-missing behavior, runtime commands, SQL reconciliation, conflict, and rollback guidance in specs/001-etl-run-reliability/quickstart.md.

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): No code initialization is required.
- Foundational (Phase 2): T001 precedes T002. After T002, T003 and T004 can proceed in parallel. T005 and T006 follow T004 and can proceed in parallel.
- User Stories (Phase 3+): User Story 1 starts after Phase 2. User Story 2 follows User Story 1 because both use the same runner transaction and stage sequence.
- Polish (Phase 5): T016 follows implementation of both stories.

### User Story Dependencies

- User Story 1 (P1): Starts after Phase 2; MVP scope.
- User Story 2 (P1): Starts after User Story 1 establishes the shared batch transaction and stage reporting.

### Parallel Opportunities

- T003 and T004 can proceed in parallel after T002 because they edit separate files.
- T005 and T006 can proceed in parallel after T004 because they edit separate helper modules.
- Story tasks are sequential where they modify the same runner, database helper, or mapping helper.

### Parallel Example: Foundational Work

After T002:
Task: T003 in scraper/job_crawler/run_transform.py
Task: T004 in scraper/job_crawler/transform/database.py

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 2 migration, preflight, and shared-connection work.
2. Complete Phase 3 status, transaction, no_data, and Airflow skip behavior.
3. Review migration, success, empty-source, failure, and rollback scenarios from quickstart.md.

### Incremental Delivery

1. Deliver explicit migration and run outcomes with rollback.
2. Add link-preserving upsert and current mappings.
3. Update the quickstart to reflect the implemented behavior.

## Notes

- The migration does not change job or mapping columns and does not delete existing rows.
- Raw jobs schema setup by the crawler remains outside this clean-schema migration.
- No new runtime dependency or automated test suite is planned.
- The schema migration must be applied before running transform.
