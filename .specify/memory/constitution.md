<!--
Sync Impact Report
- Version change: none → 1.0.0 (initial ratification)
- Established principles: Source Identity and Traceability; Repeatable ETL;
  Explicit Run Outcomes; Preserve Valid Data; Protected Access
- Added sections: Architecture and Data Constraints; Change and Verification Workflow
- Removed sections: none
- Follow-up TODO: confirm the original ratification date
- Amendment 2026-11-09: Version 1.0.0 → 1.1.0 (MINOR). Use Scrapy for current and new source adapters; remove the Crawlee proposal while preserving the requirement for measured evidence before any future framework change.
-->

# IT Job ETL Pipeline Constitution

## Core Principles

### I. Source Identity and Traceability
Every job record MUST retain its source label and available source identifier or canonical link. Source labels MUST NOT be rewritten, and records from different sources MUST NOT be merged, until the source identity and equivalence are verified against a live URL or authoritative record.

### II. Repeatable ETL
ETL writes MUST be safe to replay and MUST update changed content using a documented natural key. Job rows and dependent mappings MUST be processed in dependency order. When source content changes, obsolete mappings MUST be removable as well as new mappings being added.

### III. Explicit Run Outcomes
A crawl or transform run MUST distinguish a valid empty result from request, authentication, parsing, and database failures. A failure that prevents required output MUST propagate to the orchestrator; logging an error and reporting success is prohibited. Run summaries MUST expose counts and failures by source and stage where those counts are available.

### IV. Preserve Valid Data
A failed, blocked, or incomplete detail fetch MUST NOT erase previously stored non-empty data. Detail-fetch status and content quality MUST be represented separately so that retries can target incomplete records without mislabeling them as successful.

### V. Protected Access
Credentials and authenticated session state MUST stay out of version control and application logs. Crawlers MUST use access methods permitted by the source and apply source-specific request limits, retry behavior, and authentication-state handling.

## Architecture and Data Constraints

Source-specific parsing MUST remain isolated from the shared job data contract and downstream ETL. The current platform uses PostgreSQL, Airflow, Scrapy, Flask, and Power BI. The current and new source adapters MUST use the existing Scrapy-based crawler package. Any future framework change MUST be proposed in a bounded spec and justified by measured comparison recorded in the plan. Schema changes MUST use explicit migrations rather than DDL executed on every ETL run.

URLs, source aliases, database availability, and crawl coverage MUST be treated as unverified until checked against the live environment or source. Historical audit logs alone are not proof of current data state.

## Change and Verification Workflow

Changes MUST have a bounded specification, implementation plan, dependency-ordered tasks, and a consistency review before implementation. After implementation, the code and artifacts MUST be checked against the specification until remaining gaps are either resolved or recorded as follow-up tasks.

Verification MUST use evidence from the affected layer. Pipeline claims SHOULD be supported by run counts and raw-to-clean reconciliation; source claims SHOULD be checked against representative live pages when the source is available. Checks that require unavailable services MUST be reported as not verified, with the limitation stated. Checklist items MUST only be marked complete when their stated criterion has supporting evidence.

## Governance

This constitution governs project planning and implementation. Amend it when project rules change, record the reason in the sync impact report, and update the version using semantic versioning: MAJOR for incompatible rule changes, MINOR for new or materially expanded rules, and PATCH for clarifications that do not change intent. Reviewers MUST check new plans and implementation results against these principles. Requirements that depend on unverified external state remain explicit follow-up items until evidence is available.

The original ratification date is not present in the repository and must be confirmed.

**Version**: 1.1.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm original adoption date | **Last Amended**: 2026-11-09
