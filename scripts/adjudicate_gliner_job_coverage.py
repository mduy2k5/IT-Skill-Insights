"""Adjudicate GLiNER coverage proposals and expand repeated skill mentions.

All decisions in this file are an AI first pass. The resulting annotations are
kept separate from the original review queue and are not human gold labels.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data/staging/saramin/embedded_jobs_2026-11-09.json"
AI_REVIEW_PATH = ROOT / "data/gliner_finetune_ai_review.csv"
CANDIDATE_PATH = ROOT / "data/gliner_job_coverage_candidates.csv"
PREDICTIONS_PATH = ROOT / "data/gliner_job_coverage_predictions.csv"
REVIEW_OUTPUT = ROOT / "data/gliner_job_coverage_ai_review.csv"
ANNOTATION_OUTPUT = ROOT / "data/gliner_job_coverage_expanded_annotations.csv"
REPORT_OUTPUT = ROOT / "data/gliner_job_coverage_report.md"
MISSED_SPANS_OUTPUT = ROOT / "data/gliner_gold_missed_span_audit.csv"

METHOD = "technical method, protocol, or architecture"
DB = "database or query technology"
PLATFORM = "cloud or data platform"
TOOL = "software development or testing tool"
FRAMEWORK = "software framework or library"
LANG = "programming language"


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return "".join(ch for ch in value if ch.isalnum())


def exact_occurrences(text: str, surface: str):
    if not surface:
        return []
    pattern = re.compile(rf"(?<!\w){re.escape(surface)}(?!\w)", re.I)
    return [(m.start(), m.end(), text[m.start():m.end()]) for m in pattern.finditer(text)]


def is_bi_team_mention(text: str, start: int, end: int) -> bool:
    local_context = text[max(0, start - 100):min(len(text), end + 120)]
    return bool(re.search(r"Backend\s*,\s*BI\s*,\s*Data Analyst\s+(?:and|và)\s+Business", local_context, re.I))


def is_bi_system_listing(text: str, start: int, end: int) -> bool:
    local_context = text[max(0, start - 120):min(len(text), end + 150)]
    return bool(re.search(r"\(\s*CRM\s*,\s*ERP\s*,\s*BI\s*,\s*TMS\s*,\s*WMS\s*,\s*POS", local_context, re.I))


def build_rules():
    positive = {
        "big data": ("Big Data", PLATFORM, "Big Data is explicitly named as a data platform/domain in the job."),
        "hệ sinh thái dữ liệu lớn": ("Big Data platform ecosystem", PLATFORM, "The phrase explicitly identifies a Big Data ecosystem in a technical infrastructure responsibility."),
        "nền tảng dữ liệu tập trung": ("centralized data platform", PLATFORM, "The job explicitly requires building data pipelines on a centralized data platform."),
        "zookeeper": ("ZooKeeper", FRAMEWORK, "Named distributed-systems technology in the Hadoop stack."),
        "sql": ("SQL", DB, "SQL is a database query technology; the model's programming-language label is incorrect."),
        "mysql": ("MySQL", DB, "Named relational database technology."),
        "postgre": ("PostgreSQL", DB, "The source contains a truncated PostgreSQL name; preserve its exact surface."),
        "postgresql": ("PostgreSQL", DB, "Named relational database technology."),
        "csdl": ("database", DB, "Vietnamese abbreviation for database, explicitly used in a DBA job."),
        "co so du lieu": ("database", DB, "Database technology named as a core job responsibility."),
        "csdl oracle": ("Oracle Database", DB, "Oracle database technology named in the source."),
        "automatic storage management asm": ("Oracle ASM", DB, "Named Oracle database storage technology."),
        "asm": ("Oracle ASM", DB, "Oracle ASM is named as a database technology in this context."),
        "relational databases": ("relational databases", DB, "Relational databases are explicitly listed as required knowledge."),
        "databases": ("databases", DB, "Database knowledge is explicitly required in this data role."),
        "database": ("database", DB, "Database technology is explicitly named in the source."),
        "sql server": ("SQL Server", DB, "Named relational database technology."),
        "oracle": ("Oracle Database", DB, "Oracle is a named database technology in this DBA context."),
        "api": ("API", METHOD, "API is an integration protocol/interface in this source context."),
        "apis": ("API", METHOD, "API is an integration protocol/interface in this source context."),
        "rest apis": ("REST API", METHOD, "Named API protocol used for integrations."),
        "webhooks": ("Webhook", METHOD, "Named event-driven integration mechanism."),
        "api keys": ("API key authentication", METHOD, "Authentication mechanism explicitly named in a technical requirements list."),
        "api based": ("API-based integration", METHOD, "Integration pattern explicitly named in the source."),
        "event driven architecture": ("event-driven architecture", METHOD, "Architecture pattern explicitly required."),
        "event driven integrations": ("event-driven integration", METHOD, "Integration pattern explicitly listed."),
        "batch": ("batch processing", METHOD, "Batch processing is an explicit data integration pattern."),
        "batch files": ("batch/file-based integration", METHOD, "File-based batch integration method explicitly named."),
        "workflows": ("workflow orchestration", METHOD, "Workflow orchestration is a stated technical capability in context."),
        "data pipelines": ("data pipelines", METHOD, "Pipeline construction and operation are central data engineering skills."),
        "pipelines": ("data pipelines", METHOD, "Data pipelines are explicit technical objects in the source context."),
        "pipeline": ("data pipelines", METHOD, "Data pipeline construction and operation are technical skills."),
        "data platforms": ("data platform", PLATFORM, "The source describes development on data platforms."),
        "data lakehouse": ("data lakehouse", METHOD, "Lakehouse is a data architecture concept in the source."),
        "data warehouse": ("data warehouse", METHOD, "Data warehouse architecture is explicitly named."),
        "dwh": ("data warehouse", METHOD, "DWH is the source's abbreviation for data warehouse."),
        "datalake": ("data lake", METHOD, "Data lake architecture is explicitly named."),
        "data lake": ("data lake", METHOD, "Data lake architecture is explicitly named."),
        "datamart": ("data mart", METHOD, "Data mart architecture is explicitly named."),
        "data mart": ("data mart", METHOD, "Data mart architecture is explicitly named."),
        "etl": ("ETL", METHOD, "ETL is a data integration/transformation method."),
        "etl elt": ("ETL/ELT", METHOD, "ETL/ELT is a data integration/transformation method."),
        "delta": ("Delta Lake", PLATFORM, "Delta is named with Parquet and Iceberg as a data storage format/platform."),
        "event driven architecture": ("event-driven architecture", METHOD, "Architecture pattern explicitly required."),
        "integration methods": ("data integration methods", METHOD, "The source explicitly asks to define integration patterns."),
        "data extraction": ("data extraction", METHOD, "Data extraction is named as a technical workflow stage."),
        "data mappings": ("data mapping", METHOD, "Data mapping is a technical data integration task."),
        "mapping": ("data mapping", METHOD, "Mapping is described as a data transformation stage."),
        "transformation rules": ("data transformation", METHOD, "Transformation rules are an explicit data integration method."),
        "transformations": ("data transformation", METHOD, "Data transformation is a core data-engineering skill."),
        "integration patterns": ("integration patterns", METHOD, "Reusable integration patterns are an explicit engineering practice."),
        "queues": ("message queues", METHOD, "Queues are explicitly listed with event-driven architecture and asynchronous processing."),
        "scheduled": ("scheduled integration", METHOD, "Scheduled is an explicit integration pattern in this source."),
        "dependencies": ("workflow dependency management", METHOD, "Workflow dependencies are an explicit design concern in the integration job."),
        "integration health assessment frameworks": ("integration health assessment", METHOD, "A technical framework for assessing integration health is explicitly named."),
        "bi and visualization tools": ("BI and visualization tools", TOOL, "The job explicitly requires building dashboards with BI/visualization tools."),
        "rag pipeline": ("RAG pipeline", METHOD, "Retrieval-augmented generation pipeline is explicitly required."),
        "phát triển phần mềm": ("software development", METHOD, "Software development experience is explicitly required."),
        "điện toán đám mây": ("cloud computing", PLATFORM, "Cloud computing is explicitly named as the product domain."),
        "integration layers": ("integration architecture", METHOD, "Integration layers are an explicit technical architecture concept."),
        "system integrations": ("system integration", METHOD, "System integrations are explicitly named technical work."),
        "integration": ("system integration", METHOD, "Integration is an explicit technical responsibility in context."),
        "go live": ("production go-live", METHOD, "Production go-live is an explicit deployment process in this job."),
        "cloud": ("cloud platform", PLATFORM, "Cloud infrastructure/platform is a stated technical domain."),
        "aws": ("AWS", PLATFORM, "Named cloud platform in the source."),
        "github": ("GitHub", TOOL, "Named source-control and collaboration platform in a software workflow."),
        "linux": ("Linux", PLATFORM, "Linux server administration is explicitly required."),
        "ml dl": ("machine learning/deep learning", METHOD, "ML/DL pipelines and model optimization are explicitly named."),
        "kaggle": ("Kaggle", TOOL, "Named data-science competition platform relevant to the role."),
        "numerai": ("Numerai", TOOL, "Named quantitative-research competition platform relevant to the role."),
        "git": ("Git", TOOL, "Git is a named source-control tool when used as a technical skill."),
        "linear algebra": ("linear algebra", METHOD, "Mathematical foundation explicitly required for quantitative model development."),
        "statistics": ("statistics", METHOD, "Statistical foundation explicitly required for quantitative model development."),
        "probability": ("probability", METHOD, "Mathematical foundation explicitly required for quantitative model development."),
        "calculus": ("calculus", METHOD, "Mathematical foundation explicitly required for quantitative model development."),
        "kaggle": ("Kaggle", TOOL, "Named quantitative/ML competition platform in a relevant experience requirement."),
        "numerai": ("Numerai", TOOL, "Named quantitative-research competition platform in a relevant experience requirement."),
        "claude": ("Claude", TOOL, "Named AI assistant used as a work tool in the job description."),
        "gemini": ("Gemini", TOOL, "Named AI assistant used as a work tool in the job description."),
        "codex": ("Codex", TOOL, "Named AI coding assistant in the job description."),
    }
    negative = {
        "amazon": ("out_of_scope", "Subspan of Amazon Bedrock, not a separate skill mention."),
        "tiếng anh": ("out_of_scope", "Natural-language requirement, outside the six technical entity labels."),
        "english": ("out_of_scope", "Natural-language requirement, outside the six technical entity labels."),
        "tiếng nhật": ("out_of_scope", "Natural-language requirement, outside the six technical entity labels."),
        "tiếng việt": ("out_of_scope", "Natural-language requirement, outside the six technical entity labels."),
        "ngôn ngữ khác": ("out_of_scope", "Generic natural-language reference, outside the six technical entity labels."),
        "ngôn ngữ": ("out_of_scope", "Generic natural-language reference, not a named programming language."),
        "prd": ("reject_background", "Project requirements document, not a technical skill entity."),
        "ai": ("reject_background", "Generic AI mention without a specific tool or method."),
        "llm": ("out_of_scope", "Generic model family mention, not a concrete skill/tool under this taxonomy."),
        "slack": ("out_of_scope", "Communication application named under the job's communication tools, not a technical skill requirement."),
        "notion": ("out_of_scope", "Documentation/collaboration application named under communication tools, not a technical skill requirement."),
        "salesnow": ("out_of_scope", "Employer name."),
        "kotoshikou": ("out_of_scope", "Company value/motto, not a technical skill."),
        "b2b saas": ("out_of_scope", "Business/product model, not a technical skill entity."),
        "reusable frameworks": ("reject_background", "Generic phrase, not a named software framework."),
        "dashboard templates": ("reject_background", "Generic deliverable/template phrase, not a named tool or method."),
        "data analyst": ("reject_background", "Role/team reference, not a technical entity span."),
        "data engineering and data analysts": ("reject_background", "Collaborating team/role names, not a technical skill entity."),
        "backend": ("reject_background", "Role/team reference, not a technical entity span."),
        "business": ("reject_background", "Business team reference, not a technical entity span."),
        "dev": ("reject_background", "Role/team abbreviation, not a technical entity span."),
        "ba": ("reject_background", "Business analyst role abbreviation, not a technical entity span."),
        "tester qa": ("reject_background", "Role reference, not a technical skill entity."),
        "checklist": ("reject_background", "Generic project artifact, not a technical skill entity."),
        "bi tools": ("reject_background", "Generic section category; concrete BI products are named separately."),
        "workflow history": ("reject_background", "Operational evidence source, not a technical skill entity."),
        "system a": ("reject_background", "Generic placeholder system name, not a named platform."),
        "datasets": ("reject_background", "Generic data artifact, not a technical skill entity."),
        "source systems": ("reject_background", "Generic data-source phrase, not a named system or method."),
        "downstream reporting": ("reject_background", "Reporting output/use case, not a specific technical skill."),
        "api responses": ("reject_background", "API response data used for troubleshooting, not a skill entity."),
        "tbp": ("out_of_scope", "Vietnamese department-head abbreviation in context, not a technical entity."),
        "mb bank": ("out_of_scope", "Employer name, not a technical skill."),
        "jlpt n3": ("out_of_scope", "Natural-language proficiency certification, outside the six technical labels."),
        "crawl": ("reject_background", "Verb describing website collection activity, not a distinct technical method span."),
        "market microstructure": ("out_of_scope", "Financial-market domain knowledge, outside the technical-skill taxonomy."),
        "technical indicators": ("out_of_scope", "Financial trading-analysis concept, outside the technical-skill taxonomy."),
        "phần mềm": ("reject_background", "Generic word for software, not a named tool or method."),
        "công cụ tương đương": ("reject_background", "Generic placeholder, not a named software tool."),
        "công nghệ kỹ thuật điện tử viễn thông": ("out_of_scope", "Education/degree field, not a technical skill entity."),
        "công nghệ kỹ thuật điều khiển tự động hóa": ("out_of_scope", "Education/degree field, not a technical skill entity."),
        "kỹ thuật điện tử viễn thông": ("out_of_scope", "Education/degree field, not a technical skill entity."),
        "công nghệ kỹ thuật điện điện tử": ("out_of_scope", "Education/degree field, not a technical skill entity."),
        "điện tử viễn thông": ("out_of_scope", "Education/degree field, not a technical skill entity."),
        "performance": ("reject_background", "Generic performance word, not a specific technical method span."),
        "data tools": ("reject_background", "Generic category heading; the concrete tools are named separately."),
        "data engineering": ("out_of_scope", "Role/domain phrase rather than an individual technical skill."),
        "data analyst and data engineering": ("reject_background", "Team/role reference, not a technical entity span."),
        "phân tích dữ liệu": ("reject_background", "In this responsibility it names a collaborating team, not an individual skill."),
        "vận hành và nghiệp vụ": ("reject_background", "Generic collaborating teams, not technical skill entities."),
        "nhóm phát triển sản phẩm": ("reject_background", "Team reference, not a technical skill entity."),
        "metadata sql query engine": ("reject_background", "Section heading/category label, not one technical skill mention."),
        "bi visualization tools": ("reject_background", "Generic section heading; specific BI tools are named separately."),
        "công cụ": ("reject_background", "Generic word for tool, not a named technical tool."),
        "crm": ("reject_background", "Core business application listed as a system served by the database, not a requested skill here."),
        "erp": ("reject_background", "Core business application listed as a system served by the database, not a requested skill here."),
        "tms": ("reject_background", "Core business application listed as a system served by the database, not a requested skill here."),
        "wms": ("reject_background", "Core business application listed as a system served by the database, not a requested skill here."),
        "pos": ("reject_background", "Core business application listed as a system served by the database, not a requested skill here."),
        "ibm": ("out_of_scope", "Vendor name without a named product or technical skill."),
        "toeic": ("out_of_scope", "Language certification, outside the six technical entity labels."),
        "ielts": ("out_of_scope", "Language certification, outside the six technical entity labels."),
        "ecommerce": ("out_of_scope", "Business domain/platform category, not a technical skill in this context."),
        "loyalty": ("out_of_scope", "Business domain concept, not a technical skill in this context."),
        "martech": ("out_of_scope", "Business/marketing technology domain label, not a concrete tool or method."),
        "billing": ("out_of_scope", "Business system category in a domain list, not a technical skill requirement."),
        "professional services": ("out_of_scope", "Business-services model, not a technical skill entity."),
        "customer": ("reject_background", "Generic business noun, not a technical skill entity."),
        "customer source systems": ("reject_background", "Generic data-source phrase, not a named platform or method."),
        "source data": ("reject_background", "Generic data artifact, not a technical skill entity."),
        "reports": ("reject_background", "Generic output artifact, not a named reporting tool."),
        "dashboards": ("reject_background", "Generic output artifact, not a named BI tool."),
    }
    return {norm(k): v for k, v in positive.items()}, {norm(k): v for k, v in negative.items()}


def main():
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    jobs = {str(job["id"]): job for job in raw["jobs"]}
    positives, negatives = build_rules()

    existing_by_job_section_surface = defaultdict(list)
    existing_spans = set()
    with AI_REVIEW_PATH.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("ai_decision") not in {"approve_positive", "repair_positive"}:
                continue
            jid = str(row["job_id"])
            section = row.get("ai_approved_section", "")
            skill = row.get("ai_approved_skill", "")
            surface = row.get("ai_approved_surface", "")
            label = row.get("ai_approved_gliner_label", "")
            if jid and section and skill and surface and label:
                existing_by_job_section_surface[(jid, section, norm(surface))].append((skill, label, surface))
                try:
                    existing_spans.add((jid, section, int(row["span_start_char"]), int(row["span_end_char_exclusive"]), label))
                except (KeyError, ValueError, TypeError):
                    pass

    # Expand every exact repeated surface from an already approved candidate.
    expanded = {}
    for (jid, section, _), decisions in existing_by_job_section_surface.items():
        text = jobs[jid].get(section + "_text") or ""
        for skill, label, surface in decisions:
            for start, end, actual in exact_occurrences(text, surface):
                key = (jid, section, start, end, label)
                if key in existing_spans or key in expanded:
                    continue
                if norm(surface) == "bi" and (is_bi_team_mention(text, start, end) or is_bi_system_listing(text, start, end)):
                    expanded[key] = {
                        "candidate_id": "REPEAT-" + jid + "-" + str(start),
                        "job_id": jid,
                        "job_title": jobs[jid].get("title", ""),
                        "section": section,
                        "start_char": start,
                        "end_char_exclusive": end,
                        "surface": actual,
                        "model_labels": "",
                        "model_scores": "",
                        "review_match": "repeat_non_skill_context",
                        "ai_decision": "reject_background",
                        "approved_skill": "",
                        "approved_gliner_label": "",
                        "confidence": "high",
                        "rationale": "BI is listed as a collaborating team or an application served by the database, not as a skill mention.",
                        "human_decision": "",
                        "human_approved_surface": "",
                        "human_approved_section": "",
                        "human_approved_skill": "",
                        "human_approved_gliner_label": "",
                        "human_notes": "",
                    }
                    continue
                expanded[key] = {
                    "candidate_id": "REPEAT-" + jid + "-" + str(start),
                    "job_id": jid,
                    "job_title": jobs[jid].get("title", ""),
                    "section": section,
                    "start_char": start,
                    "end_char_exclusive": end,
                    "surface": actual,
                    "model_labels": "",
                    "model_scores": "",
                    "review_match": "repeat_existing_skill",
                    "ai_decision": "approve_repeat_positive",
                    "approved_skill": skill,
                    "approved_gliner_label": label,
                    "confidence": "high",
                    "rationale": "Exact repeated mention of a skill already reviewed in this job and section.",
                    "human_decision": "",
                    "human_approved_surface": "",
                    "human_approved_section": "",
                    "human_approved_skill": "",
                    "human_approved_gliner_label": "",
                    "human_notes": "",
                }

    with CANDIDATE_PATH.open(encoding="utf-8-sig", newline="") as handle:
        raw_candidates = list(csv.DictReader(handle))
    grouped = defaultdict(list)
    for row in raw_candidates:
        key = (row["job_id"], row["section"], int(row["start_char"]), int(row["end_char_exclusive"]), row["surface"])
        grouped[key].append(row)

    reviewed = []
    new_approved = {}
    for (jid, section, start, end, surface), items in grouped.items():
        labels = sorted({item["proposed_gliner_label"] for item in items})
        score_by_label = {label: max(float(item["score"]) for item in items if item["proposed_gliner_label"] == label) for label in labels}
        key = (jid, section, start, end)
        prior = existing_by_job_section_surface.get((jid, section, norm(surface)), [])
        matched = next((p for p in prior), None)
        rule = positives.get(norm(surface))
        reject = negatives.get(norm(surface))
        confidence = "medium"

        source_text = jobs[jid].get(section + "_text") or ""
        if norm(surface) == "bi" and (is_bi_team_mention(source_text, start, end) or is_bi_system_listing(source_text, start, end)):
            decision = "reject_background"
            rationale = "BI is listed as a collaborating team or an application served by the database, not as a skill mention."
            skill = label = ""
            confidence = "high"
        elif matched:
            skill, label, _ = matched
            decision = "approve_repeat_positive"
            rationale = "This exact technical surface was already reviewed as a skill in the same job section; add the repeated occurrence."
            confidence = "high"
        elif rule:
            skill, label, rationale = rule
            decision = "approve_positive"
            confidence = "high" if max(score_by_label.values()) >= 0.4 else "medium"
        elif reject:
            decision, rationale = reject
            skill = label = ""
            confidence = "high" if max(score_by_label.values()) >= 0.4 else "medium"
        elif jid == "2143574" and section == "responsibilities" and norm(surface) == norm("phân tích dữ liệu"):
            decision, rationale = "reject_background", "Here it names a collaborating team, not an individual skill requirement."
            skill = label = ""
            confidence = "high"
        else:
            decision = "needs_review"
            skill = label = ""
            rationale = "Candidate not covered by the conservative skill/context rules; keep out of train until reviewed."
            confidence = "low"

        row = {
            "candidate_id": f"GLC-{len(reviewed)+1:04d}",
            "job_id": jid,
            "job_title": jobs[jid].get("title", ""),
            "section": section,
            "start_char": start,
            "end_char_exclusive": end,
            "surface": surface,
            "model_labels": " | ".join(labels),
            "model_scores": " | ".join(f"{label}={score_by_label[label]:.4f}" for label in labels),
            "review_match": "same_skill_repeat" if matched else "new_span",
            "ai_decision": decision,
            "approved_skill": skill,
            "approved_gliner_label": label,
            "confidence": confidence,
            "rationale": rationale,
            "human_decision": "",
            "human_approved_surface": "",
            "human_approved_section": "",
            "human_approved_skill": "",
            "human_approved_gliner_label": "",
            "human_notes": "",
        }
        reviewed.append(row)
        if decision == "approve_positive":
            new_approved[key + (label,)] = row

    review_rows = list(expanded.values()) + reviewed
    review_fields = list(review_rows[0]) if review_rows else []
    with REVIEW_OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields)
        writer.writeheader()
        writer.writerows(review_rows)

    annotation_rows = [
        row for row in review_rows
        if row["ai_decision"] in {"approve_positive", "approve_repeat_positive"}
    ]
    annotation_fields = list(annotation_rows[0]) if annotation_rows else []
    with ANNOTATION_OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=annotation_fields)
        writer.writeheader()
        writer.writerows(annotation_rows)

    with AI_REVIEW_PATH.open(encoding="utf-8-sig", newline="") as handle:
        missed_rows = [row for row in csv.DictReader(handle) if row.get("candidate_kind") == "gold_missed_candidate"]
    missed_fields = [
        "candidate_id", "split", "job_id", "job_title", "candidate_kind", "candidate_skill",
        "source_section", "source_surface", "span_start_char", "span_end_char_exclusive",
        "proposed_gliner_label", "context", "human_decision", "approved_surface",
        "approved_section", "approved_gliner_label", "notes",
        "ai_decision", "ai_approved_skill", "ai_approved_surface",
        "ai_approved_section", "ai_approved_gliner_label", "ai_review_confidence",
        "ai_review_rationale",
    ]
    with MISSED_SPANS_OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=missed_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(missed_rows)

    decisions = Counter(row["ai_decision"] for row in review_rows)
    per_section = defaultdict(Counter)
    for row in review_rows:
        per_section[(row["job_id"], row["section"])][row["ai_decision"]] += 1

    missed_per_section = defaultdict(Counter)
    for row in missed_rows:
        section = row.get("ai_approved_section") or row.get("source_section") or "unknown"
        decision = row.get("ai_decision", "")
        key = "resolved" if decision in {"approve_positive", "repair_positive"} else "excluded" if decision in {"out_of_scope", "reject_background"} else "pending"
        missed_per_section[(str(row.get("job_id", "")), section)][key] += 1
    missed_decisions = Counter(row.get("ai_decision", "") for row in missed_rows)
    missed_pending = sum(v for k, v in missed_decisions.items() if k not in {"approve_positive", "repair_positive", "out_of_scope", "reject_background"})
    with PREDICTIONS_PATH.open(encoding="utf-8-sig", newline="") as handle:
        total_proposals = sum(1 for _ in csv.DictReader(handle))

    report = [
        "# Kiểm toán độ phủ skill theo job (AI first pass)",
        "",
        "> Đây là lượt AI rà soát ứng viên do GLiNER đề xuất, chưa phải nhãn người xác nhận. Mô hình chỉ tạo danh sách ứng viên; các quyết định `approve`/`reject` dựa trên rule taxonomy và ngữ cảnh job, không lấy score làm nhãn chuẩn.",
        "",
        "## Tổng quan",
        "",
        f"- Job đã quét: `{len(jobs)}`; section có nội dung: `28`.",
        f"- Span GLiNER chưa có trong review trước: `{len(grouped)}` (gộp theo vị trí span, gộp các nhãn dự đoán trùng span).",
        f"- Lượt AI review mới, gồm cả các lần nhắc lặp lại của skill đã duyệt: `{len(review_rows)}`.",
        f"- Kết quả: `{dict(decisions)}`.",
        f"- Model tạo `{total_proposals}` proposal tổng cộng ở threshold `0.15`; `{len(raw_candidates)}` proposal chưa được review trước, trong đó `{sum(float(r['score']) >= 0.4 for r in raw_candidates)}` đạt `0.40`. Threshold thấp chỉ dùng để mở rộng danh sách ứng viên, không dùng làm quyết định nhãn.",
        f"- Queue benchmark có `{len(missed_rows)}` mục GLiNER từng bỏ sót; `{missed_decisions['approve_positive'] + missed_decisions['repair_positive']}` mục được AI gắn với span nguyên văn trong job, `{missed_decisions['out_of_scope'] + missed_decisions['reject_background']}` mục bị loại khỏi phạm vi, `{missed_pending}` mục còn thiếu quyết định/span.",
        "- Lượt này vẫn là AI first pass: ứng viên đến từ benchmark cũ và dự đoán GLiNER ở ngưỡng thấp. Nó không chứng minh rằng mọi skill trong toàn bộ mô tả đã được tìm thấy.",
        "",
        "## Các skill benchmark bị bỏ sót: span nguồn đã đối chiếu",
        "",
        "Span tiếng Việt/tiếng Anh tương đương được ghi theo đúng vị trí nguyên văn trong section nguồn. Các mục cùng trỏ vào một span được giữ để rà soát, nhưng bộ chuyển đổi train sẽ gộp span trùng cùng nhãn.",
        "",
        "| Job | Section cuối | Đã gắn span | Ngoài phạm vi | Còn cần xử lý |",
        "|---|---|---:|---:|---:|",
    ]
    for jid, job in jobs.items():
        for section in ("requirements", "responsibilities"):
            c = missed_per_section[(jid, section)]
            if c.total():
                title = job.get("title", "").replace("|", "/")
                report.append(f"| `{jid}` {title} | {section} | {c['resolved']} | {c['excluded']} | {c['pending']} |")
    report.extend([
        "",
        "## Theo từng job/section",
        "",
        "| Job | Section | Repeat positive | New positive | Rejected/out of scope | Needs review |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for jid, job in jobs.items():
        for section in ("requirements", "responsibilities"):
            c = per_section[(jid, section)]
            if not (job.get(section + "_text") or ""):
                continue
            title = job.get("title", "").replace("|", "/")
            report.append(f"| `{jid}` {title} | {section} | {c['approve_repeat_positive']} | {c['approve_positive']} | {c['reject_background'] + c['out_of_scope']} | {c['needs_review']} |")
    report.extend([
        "",
        "## Quy tắc tránh false negative",
        "",
        "Không coi mọi token chưa được gán là negative. Chỉ lấy positive span đã duyệt; chunk giao với `needs_review`/`needs_span` phải bị loại khỏi train. Vì GLiNER chỉ đề xuất ứng viên, một section không còn ứng viên pending vẫn chưa đồng nghĩa là exhaustive gold; cần rà toàn văn độc lập trước khi dùng train negatives để kết luận về chất lượng fine-tune.",
        "",
        "## Tệp",
        "",
        f"- Review đầy đủ: `{REVIEW_OUTPUT.relative_to(ROOT).as_posix()}`",
        f"- Positive annotations mở rộng: `{ANNOTATION_OUTPUT.relative_to(ROOT).as_posix()}`",
        f"- Đối chiếu các mục benchmark GLiNER bỏ sót: `{MISSED_SPANS_OUTPUT.relative_to(ROOT).as_posix()}`",
        "- Prediction audit thô: `data/gliner_job_coverage_predictions.csv`",
        "",
    ])
    REPORT_OUTPUT.write_text("\n".join(report), encoding="utf-8")

    print("Model candidates grouped by source span:", len(grouped))
    print("Repeated existing skill mentions expanded:", len(expanded))
    print("AI review rows:", len(review_rows), dict(decisions))
    print("Wrote", REVIEW_OUTPUT)
    print("Wrote", ANNOTATION_OUTPUT)
    print("Wrote", MISSED_SPANS_OUTPUT)
    print("Wrote", REPORT_OUTPUT)
    print("Sections still requiring review:")
    for (jid, section), c in sorted(per_section.items()):
        if c["needs_review"]:
            print(f"  {jid} {section}: {c['needs_review']}")


if __name__ == "__main__":
    main()
