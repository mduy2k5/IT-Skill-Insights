# ETL Reliability Checklist: Độ tin cậy của lượt ETL

**Purpose**: Review whether the ETL reliability requirements are complete, clear, consistent, and measurable
**Created**: 2026-11-03
**Feature**: [spec.md](../spec.md)

**Note**: This custom checklist is a reviewer-owned requirements-quality review artifact.
**Review Ownership**: Mark an item [x] only when the reviewer determines that its requirements-quality criterion is satisfied.
**Marker Semantics**: [x] means the criterion is reviewed and satisfied for requirements quality. It does not mean implementation work is complete.

## Requirement Completeness

- [x] CHK001 Are success, no-data, and failure outcomes specified as separate states? [Completeness, Spec §FR-001]
- [x] CHK002 Does the run summary specify input, normalized, new, updated, unchanged, mapping-added, and mapping-removed counts by source? [Completeness, Spec §FR-002]
- [x] CHK003 Are the required stages named and are downstream stages stopped after a required-stage failure? [Completeness, Spec §FR-004]
- [x] CHK004 Does the failure requirement name both the failing stage and enough error detail for an operator to investigate? [Completeness, Spec §FR-005]
- [x] CHK005 Does the rollback requirement preserve prior committed data while undoing writes from the failed batch? [Recovery, Spec §FR-007]

## Requirement Clarity

- [x] CHK006 Is the source-label rule clear, including the decision not to infer which website WebA represents? [Traceability, Spec §FR-008]
- [x] CHK007 Are the normalized fields covered by an update to an existing link stated explicitly? [Clarity, Spec §FR-009]
- [x] CHK008 Are the title, skill, and level mapping refresh triggers and stale-link removal behavior explicit? [Clarity, Spec §FR-010]
- [x] CHK009 Is a valid job with no dictionary match distinguished from a processing error? [Clarity, Spec §FR-006]
- [x] CHK010 Does the specification define what happens when a link already belongs to another source label? [Edge Case, Spec §FR-013]

## Requirement Consistency

- [x] CHK011 Do the no-match requirements agree with the requirement to remove mappings that no longer match changed content? [Consistency, Spec §FR-006, FR-010]
- [x] CHK012 Do the failure-state requirements agree with the empty-input outcome and its success criteria? [Consistency, Spec §FR-001, SC-003]
- [x] CHK013 Is the normalized-job update scope consistent with the stated exclusion for raw-crawler updates and matching-rule changes? [Consistency, Spec §FR-009, FR-012]
- [x] CHK014 Is replaying unchanged content clearly defined as producing no duplicate jobs or mappings? [Consistency, Spec §FR-011, User Story 2 Scenario 5]

## Acceptance Criteria Quality

- [x] CHK015 Can every success criterion be assessed with counts, states, or a defined source-label comparison? [Measurability, Spec §Success Criteria]
- [x] CHK016 Do the measurable outcomes cover successful batches, controlled failures, empty input, run summaries, and changed existing jobs? [Coverage, Spec §Success Criteria]

## Scenario and Edge-Case Coverage

- [x] CHK017 Do the scenarios cover new jobs, changed jobs, unchanged replays, and jobs with no match? [Coverage, User Story 2]
- [x] CHK018 Are valid empty input, unreadable dictionaries, partial writes, and source-link conflicts included as edge cases? [Coverage, Spec §Edge Cases]
- [x] CHK019 Is the one-source scope and the treatment of other source labels explicit? [Scope, Spec §FR-008, FR-013]

## Non-Functional Requirements

- [x] CHK020 Is the absence of a new throughput or latency target intentional and stated for this bounded feature? [Assumption, Spec §Assumptions]
- [x] CHK021 Are rollback, error-propagation, run-state, and migration-preflight outcomes distinguishable and measurable? [Coverage, Spec §FR-001, FR-004, FR-007, FR-014]

## Dependencies and Assumptions

- [x] CHK022 Are database, orchestrator, dictionary-file, and runtime-availability dependencies identified? [Dependency, Spec §Assumptions]
- [x] CHK023 Are the current source label, existing link key, and current dictionary behavior documented as assumptions? [Assumption, Spec §Assumptions]

## Ambiguities and Conflicts

- [x] CHK024 Are unresolved questions about cross-source identity, update keys, or mapping behavior either answered or explicitly out of scope? [Conflict, Spec §FR-009, FR-010, FR-013]
- [x] CHK025 Does the specification state that clean schema provisioning uses an explicit versioned migration, preserves current clean data, and fails before ETL writes when the migration is missing? [Clarity, Spec §FR-014, SC-006]
- [x] CHK026 Does the specification protect existing non-empty detail and skill mappings when raw explicitly marks the detail fetch incomplete? [Preserve Valid Data, Spec §FR-015, SC-007]

## Notes

- This checklist reviews requirement quality, not implementation behavior.
- Items start unchecked. Reviewer decisions belong to the reviewer; checked items do not mean implementation is complete.
- Focus: migration preflight, incomplete-detail preservation, failure and no-data outcomes, batch rollback, replay-safe normalized-job updates, mapping consistency, and source identity.
- Audience and timing: project reviewer before implementation; standard detail for a bounded production-pipeline change.
