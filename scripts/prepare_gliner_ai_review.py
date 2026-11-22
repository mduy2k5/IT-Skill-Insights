"""Create a Codex first-pass review of the GLiNER candidate queue.

This is explicitly AI review, not human annotation. Rows without a verifiable
source span or a defensible label remain excluded from the training pilot.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "data/gliner_finetune_review_queue.csv"
RAW_PATH = ROOT / "data/staging/saramin/embedded_jobs_2026-11-09.json"
OUTPUT_PATH = ROOT / "data/gliner_finetune_ai_review.csv"

LABELS = {
    "programming language",
    "software framework or library",
    "database or query technology",
    "cloud or data platform",
    "software development or testing tool",
    "technical method, protocol, or architecture",
}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return "".join(ch for ch in value if ch.isalnum())


def exact_occurrences(text: str, surface: str) -> list[tuple[int, int, str]]:
    if not surface:
        return []
    pattern = re.compile(rf"(?<!\w){re.escape(surface)}(?!\w)", re.I)
    return [(m.start(), m.end(), text[m.start():m.end()]) for m in pattern.finditer(text)]


def matching_source_span(row: dict[str, str], text: str, surface: str):
    """Use the queue's occurrence offsets when a term appears more than once."""
    matches = exact_occurrences(text, surface)
    try:
        expected = (int(row.get("span_start_char", "")), int(row.get("span_end_char_exclusive", "")))
    except (TypeError, ValueError):
        expected = None
    if expected:
        for start, end, actual in matches:
            if (start, end) == expected:
                return start, end, actual
    return matches[0] if matches else None


def is_bi_team_mention(text: str, start: int, end: int) -> bool:
    local_context = text[max(0, start - 100):min(len(text), end + 120)]
    return bool(re.search(r"Backend\s*,\s*BI\s*,\s*Data Analyst\s+(?:and|và)\s+Business", local_context, re.I))


# Clear variants where the draft skill term does not match the source wording.
# Each repair is still checked against the raw job text before it is accepted.
REPAIRS = {
    ("2142369", "queryoptimization"): ("requirements", "optimization techniques"),
    ("2142369", "workflowautomation"): ("responsibilities", "automation for data workflows"),
    ("2142369", "workflowscheduling"): ("responsibilities", "scheduling"),
    ("2138202", "ibmbigdata"): ("responsibilities", "Big Data"),
    ("2138202", "distributeddataprocessing"): ("requirements", "xử lý dữ liệu phân tán"),
    ("2138202", "distributeddatastorage"): ("requirements", "lưu trữ"),
    ("2138374", "backupandrecovery"): ("responsibilities", "Backup & Recovery"),
    ("2138374", "databasearchitecture"): ("responsibilities", "hạ tầng CSDL Oracle"),
    ("2138374", "databasesecurity"): ("responsibilities", "an toàn bảo mật CSDL Oracle"),
    ("2138374", "highavailability"): ("responsibilities", "tính sẵn sàng cao"),
    ("2138374", "monitoringandalerting"): ("responsibilities", "giám sát và cảnh báo tự động"),
    ("2138374", "postgresql"): ("requirements", "Postgre"),
    ("2139159", "automatedtesting"): ("responsibilities", "automation testing"),
    ("2139159", "loadtesting"): ("responsibilities", "load"),
    ("2139159", "manualtesting"): ("responsibilities", "manual"),
    ("2139159", "testcasedesign"): ("responsibilities", "test specifications"),
    ("2139159", "testspecificationdesign"): ("responsibilities", "test specifications"),
    ("2139159", "teststrategydevelopment"): ("responsibilities", "test strategies"),
    ("2139328", "datamigration"): ("responsibilities", "migration"),
    ("2139328", "backupandrecovery"): ("responsibilities", "khôi phục sau sự cố"),
    ("2139328", "datacenterinfrastructure"): ("responsibilities", "hạ tầng cơ sở"),
    ("2139328", "databasecapacityplanning"): ("responsibilities", "đánh giá năng lực hệ thống CSDL"),
    ("2139328", "databaseperformanceassessment"): ("responsibilities", "đánh giá năng lực hệ thống CSDL"),
    ("2139328", "databasesecurity"): ("responsibilities", "an toàn bảo mật hệ thống CSDL"),
    ("2139328", "disasterrecovery"): ("responsibilities", "khôi phục sau sự cố"),
    ("2139328", "postgresql"): ("requirements", "Postgre"),
    ("2141955", "anomalydetection"): ("responsibilities", "phát hiện bất thường"),
    ("2141955", "apiintegrations"): ("responsibilities", "tích hợp API"),
    ("2141955", "dataqualityframeworks"): ("requirements", "giám sát chất lượng dữ liệu"),
    ("2141955", "datatransformations"): ("responsibilities", "chuyển dữ liệu thô"),
    ("2141955", "deduplication"): ("responsibilities", "khử trùng lặp"),
    ("2141955", "faulttolerantpipelines"): ("responsibilities", "pipeline chịu lỗi"),
    ("2141955", "largescaledataprocessing"): ("requirements", "xử lý trên 1 triệu bản ghi mỗi ngày"),
    ("2141955", "observability"): ("responsibilities", "khả năng quan sát"),
    ("2141955", "realtimedatapipelines"): ("responsibilities", "pipeline nạp dữ liệu thời gian thực"),
    ("2141955", "relationaldatabases"): ("requirements", "cơ sở dữ liệu quan hệ"),
    ("2141955", "schemavalidation"): ("responsibilities", "kiểm tra schema"),
    ("2141955", "awslambda"): ("requirements", "Lambda"),
    ("2141955", "awss3"): ("requirements", "S3"),
    ("2141955", "airflowdagorchestration"): ("requirements", "Airflow"),
    ("2141955", "ragpipelines"): ("responsibilities", "RAG pipeline"),
    ("2141955", "sqlwindowfunctions"): ("requirements", "window function"),
    ("2141955", "vectordatabases"): ("requirements", "vector database"),
    ("2141955", "queryoptimization"): ("requirements", "tối ưu truy vấn"),
    ("2143923", "sqltroubleshooting"): ("requirements", "troubleshooting"),
    ("2143923", "workflowautomation"): ("requirements", "automated data workflows"),
    ("2143927", "datareconciliation"): ("requirements", "reconciliation"),
    ("2143927", "failurerecovery"): ("responsibilities", "recovery mechanisms"),
    ("2143927", "scheduledintegration"): ("responsibilities", "workflow scheduling"),
    ("2143927", "sqltroubleshooting"): ("requirements", "troubleshooting"),
    ("2144686", "deeplearningpipelines"): ("responsibilities", "ML/DL pipelines"),
    ("2144686", "monitoring"): ("responsibilities", "Monitor"),
    ("2144686", "productiondeployment"): ("responsibilities", "Deploy"),
    ("2144686", "systemintegration"): ("responsibilities", "integrate models into live systems"),
    ("2139603", "apiintegration"): ("requirements", "tích hợp hệ thống/API"),
    ("2139603", "apitesting"): ("requirements", "kiểm thử API"),
    ("2139603", "changecontrol"): ("responsibilities", "kiểm soát thay đổi"),
    ("2139603", "datavalidation"): ("responsibilities", "dữ liệu đầy đủ, hợp lệ"),
    ("2139603", "paymentservices"): ("requirements", "dịch vụ thanh toán"),
    ("2139603", "productiondeployment"): ("responsibilities", "triển khai production"),
    ("2139603", "qatesting"): ("requirements", "kiểm thử"),
    ("2139603", "securitycontrols"): ("responsibilities", "kiểm soát an toàn"),
    ("2139603", "systemintegration"): ("requirements", "tích hợp hệ thống/API"),
    ("2139603", "systemintegrationflow"): ("requirements", "luồng tích hợp hệ thống"),
    ("2139603", "testing"): ("requirements", "kiểm thử"),
    ("2139603", "testresultanalysis"): ("responsibilities", "ghi nhận kết quả"),
    ("2143574", "datapipelines"): ("responsibilities", "pipeline"),
    ("2143923", "bivisualization"): ("requirements", "BI/visualization"),
    ("2143923", "datareconciliation"): ("responsibilities", "reconciliation"),
    ("2143923", "datatransformation"): ("responsibilities", "transformation"),
    ("2143923", "datavalidation"): ("responsibilities", "validation"),
    ("2143574", "queryoptimization"): ("requirements", "tối ưu truy vấn"),
    ("2143574", "dataanalysis"): ("requirements", "phân tích dữ liệu"),
    ("2143574", "datacleaning"): ("responsibilities", "làm sạch"),
    ("2143574", "dataenrichment"): ("responsibilities", "làm giàu dữ liệu"),
    ("2143574", "dataintegration"): ("responsibilities", "tích hợp"),
    ("2143574", "datamodeling"): ("responsibilities", "mô hình dữ liệu"),
    ("2143574", "dataquality"): ("requirements", "chất lượng dữ liệu"),
    ("2143574", "datastandardization"): ("responsibilities", "chuẩn hóa"),
    ("2143574", "datatransformation"): ("responsibilities", "chuyển đổi"),
    ("2143574", "monitoring"): ("responsibilities", "Theo dõi"),
    ("2143574", "performanceoptimization"): ("responsibilities", "tối ưu hiệu năng"),
    ("2143574", "rdbms"): ("requirements", "cơ sở dữ liệu quan hệ"),
    ("2143574", "scheduledjobs"): ("responsibilities", "job định kỳ"),
    ("2143574", "sqlscripts"): ("responsibilities", "script xử lý dữ liệu"),
    ("2143574", "troubleshooting"): ("responsibilities", "xử lý sự cố"),
    ("2143927", "eventdrivenintegration"): ("responsibilities", "event-driven integrations"),
    ("2144325", "computernetworking"): ("responsibilities", "Networking"),
    ("2144325", "cloudarchitecture"): ("requirements", "kiến trúc Cloud"),
    ("2144325", "cybersecurity"): ("requirements", "an toàn thông tin"),
    ("2144325", "mobileappdevelopment"): ("requirements", "lập trình mobile app"),
    ("2144325", "cloudresourcemanagement"): ("responsibilities", "cấp phát tài nguyên Cloud"),
    ("2144325", "cloudserviceprovisioning"): ("responsibilities", "cung cấp và hỗ trợ dịch vụ Cloud"),
    ("2144325", "securityarchitecture"): ("responsibilities", "kiến trúc bảo mật"),
    ("2144325", "securitycompliance"): ("requirements", "quy trình tuân thủ"),
    ("2144325", "virtualization"): ("requirements", "ảo hóa"),
    ("2144325", "containers"): ("requirements", "container"),
    ("2144686", "modelperformanceoptimization"): ("responsibilities", "model performance"),
    ("2144686", "predictivemodeling"): ("responsibilities", "predictive models"),
    ("2144686", "timeseriespreprocessing"): ("requirements", "preprocessing"),
    ("2144686", "timeseriesmodeling"): ("requirements", "modeling"),
    ("2144784", "etltools"): ("requirements", "ETL tool"),
    ("2144784", "bireporting"): ("requirements", "công cụ phát triển báo cáo"),
    ("2144784", "dataanalysis"): ("requirements", "phân tích số liệu"),
    ("2144784", "dataarchitecture"): ("responsibilities", "kiến trúc hệ thống dữ liệu"),
    ("2144784", "dataintegration"): ("responsibilities", "luồng ETL dữ liệu"),
    ("2144784", "datamodeling"): ("responsibilities", "mô hình"),
    ("2144784", "dataqualitycontrols"): ("responsibilities", "kiểm soát, giảm thiểu số lượng lỗi"),
    ("2144784", "largescaledatabases"): ("requirements", "Cơ sở dữ liệu quy mô lớn"),
    ("2144784", "performanceoptimization"): ("responsibilities", "tối ưu hóa hiệu suất"),
    ("2144784", "rdbms"): ("requirements", "hệ quản trị cơ sở dữ liệu"),
    ("2144784", "reportingtools"): ("requirements", "công cụ phát triển báo cáo"),
    ("2144836", "executionplans"): ("requirements", "execution plan"),
    ("2144836", "nearreal timeprocessing"): ("responsibilities", "near real-time"),
    ("2144836", "nearrealtimeprocessing"): ("responsibilities", "near real-time"),
    ("2144836", "batchprocessing"): ("responsibilities", "xử lý batch"),
    ("2144836", "dataqualitymonitoring"): ("responsibilities", "kiểm soát chất lượng dữ liệu"),
    ("2144836", "queryoptimization"): ("responsibilities", "tối ưu hiệu năng SQL"),
    ("2144836", "streamprocessing"): ("requirements", "streaming"),
}

# Explicit first-pass taxonomy decisions for phrases whose class is not obvious
# from a named product alone. These decisions are still AI labels, not human gold.
LABEL_OVERRIDES = {
    "active data guard": ("database or query technology", "Named Oracle database availability technology.", "high"),
    "ai/ml": ("technical method, protocol, or architecture", "Machine-learning practice named in the technical stack.", "high"),
    "amazon bedrock": ("cloud or data platform", "Named managed AI platform/service.", "high"),
    "antsomi": ("cloud or data platform", "Named enterprise data platform integrated with customer systems.", "medium"),
    "apache iceberg": ("technical method, protocol, or architecture", "Open table format used in a lakehouse architecture.", "high"),
    "bi": ("technical method, protocol, or architecture", "Business intelligence is an analytics practice in this technical context.", "medium"),
    "cloud data center": ("cloud or data platform", "Named cloud and data-center infrastructure category.", "high"),
    "cloud platforms": ("cloud or data platform", "Cloud platforms are explicitly named as a technical platform category.", "medium"),
    "cloud storage": ("cloud or data platform", "Cloud storage is named as a data-platform capability.", "medium"),
    "coderabbit": ("software development or testing tool", "Named AI code review tool.", "high"),
    "codex": ("software development or testing tool", "Named AI coding assistant.", "high"),
    "data lake": ("technical method, protocol, or architecture", "Data lake is a data-storage architecture concept.", "high"),
    "data lakehouse": ("technical method, protocol, or architecture", "Lakehouse is a data-storage architecture concept.", "high"),
    "data storage systems": ("cloud or data platform", "Data-storage system category named in a platform context.", "medium"),
    "database system": ("database or query technology", "Database system is a database technology; override inconsistent model labels.", "high"),
    "dwh": ("technical method, protocol, or architecture", "DWH is a data-warehouse architecture concept.", "high"),
    "data pump": ("database or query technology", "Named Oracle database import/export utility.", "high"),
    "ecs": ("cloud or data platform", "AWS Elastic Container Service is a cloud platform service.", "high"),
    "ensemble methods": ("technical method, protocol, or architecture", "Named machine-learning method family.", "high"),
    "fact/dimension": ("technical method, protocol, or architecture", "Fact and dimension tables are dimensional data-modeling concepts.", "high"),
    "fivetran": ("cloud or data platform", "Named managed data-integration platform.", "high"),
    "hbase": ("database or query technology", "Named distributed NoSQL database in the Hadoop ecosystem.", "high"),
    "hdfs": ("cloud or data platform", "Named distributed file-storage platform in the Hadoop ecosystem.", "high"),
    "hive": ("database or query technology", "Named data warehouse and SQL query technology.", "high"),
    "hive metastore": ("cloud or data platform", "Named metadata catalog service for the data platform.", "high"),
    "html": ("programming language", "HTML is a markup language used in the software stack.", "high"),
    "iceberg": ("technical method, protocol, or architecture", "Open table format used in a lakehouse architecture.", "high"),
    "jmeter": ("software development or testing tool", "Named load-testing tool.", "high"),
    "json": ("technical method, protocol, or architecture", "JSON is a data-interchange format, not a programming language.", "high"),
    "jwt": ("technical method, protocol, or architecture", "JWT is an authentication/token standard.", "high"),
    "looker": ("software development or testing tool", "Named BI/reporting platform.", "high"),
    "mcp": ("technical method, protocol, or architecture", "Model Context Protocol is named as an integration protocol.", "high"),
    "mapreduce": ("technical method, protocol, or architecture", "Distributed data-processing programming model.", "high"),
    "metabase": ("software development or testing tool", "Named BI/reporting application.", "high"),
    "model evaluation": ("technical method, protocol, or architecture", "Model evaluation is an explicit machine-learning practice.", "high"),
    "ml/dl": ("technical method, protocol, or architecture", "Machine-learning and deep-learning practice named in the job.", "high"),
    "n8n": ("cloud or data platform", "Named workflow automation/orchestration platform.", "high"),
    "oauth 2.0": ("technical method, protocol, or architecture", "Named authentication and authorization protocol.", "high"),
    "oracle real application clusters": ("database or query technology", "Named Oracle database clustering technology.", "high"),
    "oracle rman": ("database or query technology", "Named Oracle database backup and recovery utility.", "high"),
    "parquet": ("technical method, protocol, or architecture", "Columnar data-file format named with lakehouse table formats.", "high"),
    "pig": ("software framework or library", "Apache Pig is a data-processing framework in the Hadoop ecosystem.", "high"),
    "prefect": ("cloud or data platform", "Named workflow orchestration platform.", "high"),
    "rds": ("cloud or data platform", "AWS Relational Database Service is a managed cloud service.", "high"),
    "regression": ("technical method, protocol, or architecture", "Regression is an explicitly named machine-learning method.", "high"),
    "robot framework": ("software framework or library", "Named software test-automation framework.", "high"),
    "salesnow": ("", "Employer/product name in this description, not a transferable technical skill.", "high"),
    "sftp": ("technical method, protocol, or architecture", "SFTP is a secure file-transfer protocol.", "high"),
    "sql libraries": ("", "Generic phrase without a named SQL library or technology.", "high"),
    "star schema": ("technical method, protocol, or architecture", "Star schema is a dimensional data-modeling architecture.", "high"),
    "superset": ("software development or testing tool", "Named BI/reporting application.", "high"),
    "ibm datastage": ("software development or testing tool", "Named ETL/data-integration software.", "high"),
    "vercel": ("cloud or data platform", "Named cloud application deployment platform.", "high"),
    "webhooks": ("technical method, protocol, or architecture", "Webhook is an event-driven integration mechanism.", "high"),
    "yarn": ("cloud or data platform", "Hadoop resource-management platform component.", "high"),
    "zookeeper": ("software framework or library", "Named distributed coordination service in the Hadoop ecosystem.", "high"),
    "airbyte": ("cloud or data platform", "Data integration platform named in the source.", "high"),
    "airflow dag orchestration": ("cloud or data platform", "The source names Airflow as its orchestration platform.", "high"),
    "apache nifi": ("cloud or data platform", "Named data integration platform.", "high"),
    "android": ("cloud or data platform", "Named mobile operating system/platform.", "high"),
    "baas": ("technical method, protocol, or architecture", "Banking-as-a-Service/API banking architecture concept.", "medium"),
    "cdp": ("cloud or data platform", "Customer data platform category named with other enterprise data systems.", "high"),
    "crm": ("cloud or data platform", "Enterprise customer-management platform category.", "medium"),
    "css": ("programming language", "CSS is a stylesheet language explicitly required in a software stack.", "high"),
    "compute": ("technical method, protocol, or architecture", "Cloud infrastructure capability listed alongside Storage and Networking.", "medium"),
    "core banking": ("cloud or data platform", "Named class of banking software systems.", "medium"),
    "customer 360": ("technical method, protocol, or architecture", "Customer 360 data-modeling/analytics concept in context.", "medium"),
    "customer identity": ("technical method, protocol, or architecture", "Customer identity is used as a data-modeling/identity-resolution concept.", "medium"),
    "data mart": ("technical method, protocol, or architecture", "Analytical data-warehouse structure.", "high"),
    "data warehouse": ("technical method, protocol, or architecture", "Data warehousing architecture/concept.", "high"),
    "drp": ("technical method, protocol, or architecture", "Disaster recovery planning in an infrastructure operations context.", "medium"),
    "entity resolution": ("technical method, protocol, or architecture", "Data identity resolution method.", "high"),
    "github actions": ("software development or testing tool", "Named CI/CD development tool.", "high"),
    "kpi logic": ("technical method, protocol, or architecture", "Analytical metric definition/logic used in reporting.", "medium"),
    "kpi metrics": ("technical method, protocol, or architecture", "Metric definition/maintenance in an analytics workflow.", "medium"),
    "lms": ("cloud or data platform", "Enterprise source system named in a data-integration context.", "medium"),
    "linux": ("cloud or data platform", "Named server operating-system platform.", "high"),
    "ios": ("cloud or data platform", "Named mobile operating-system platform.", "high"),
    "los": ("cloud or data platform", "Enterprise source system named in a data-integration context.", "medium"),
    "lookerstudio": ("software development or testing tool", "Named BI/reporting software.", "high"),
    "mwaa": ("cloud or data platform", "AWS Managed Workflows for Apache Airflow platform.", "high"),
    "marketingautomation": ("cloud or data platform", "Named enterprise automation platform category.", "medium"),
    "networking": ("technical method, protocol, or architecture", "Cloud infrastructure/networking capability in context.", "medium"),
    "open banking": ("technical method, protocol, or architecture", "Open Banking/API banking architecture concept.", "medium"),
    "oracle data guard": ("database or query technology", "Named Oracle database availability technology.", "high"),
    "pyspark": ("software framework or library", "Python API/framework for Apache Spark.", "high"),
    "rag pipelines": ("technical method, protocol, or architecture", "Retrieval-augmented generation pipeline explicitly named in the source.", "high"),
    "scrapy": ("software framework or library", "Named Python web-crawling framework.", "high"),
    "sql server": ("database or query technology", "Named relational database platform.", "high"),
    "storage": ("technical method, protocol, or architecture", "Cloud infrastructure capability listed with Compute and Networking.", "medium"),
    "tde": ("technical method, protocol, or architecture", "Transparent Data Encryption database security method.", "high"),
    "trino": ("database or query technology", "Named distributed SQL query engine.", "high"),
    "erp": ("cloud or data platform", "Enterprise resource planning system category named in a data integration context.", "medium"),
    "pos": ("cloud or data platform", "Point-of-sale source system category named in a data integration context.", "medium"),
    "windows": ("cloud or data platform", "Named server operating-system platform.", "high"),
    "advanced sql": ("database or query technology", "SQL query skill explicitly named.", "high"),
    "analytics": ("", "Generic analytics reference without a specific method or technology.", "high"),
    "ai data requirements": ("", "Business/data requirement phrase, not a skill entity.", "high"),
    "risk management": ("", "Financial-domain risk skill, outside this technical-skill label set.", "high"),
    "technical analysis": ("", "Financial-market analysis skill, outside this technical-skill label set.", "high"),
    "technical indicators": ("", "Financial trading indicators, outside this technical-skill label set.", "high"),
    "trading strategies": ("", "Financial trading-domain skill, outside this technical-skill label set.", "high"),
    "payment services": ("", "Business/payment domain phrase without a concrete technical entity.", "medium"),
}

METHOD_LABEL_KEYS = {
    "capacity planning", "data consistency", "data freshness", "data governance",
    "data mapping", "data quality", "data standardization", "data transformation",
    "data transformations", "data validation", "dependency management", "error handling",
    "feature engineering", "hyperparameter tuning", "idempotency", "identity resolution",
    "logging", "master data", "observability", "performance tuning", "retries",
    "schema changes", "schema validation", "segmentation", "source-to-target mappings",
    "table design", "timeout handling", "data architecture", "data integration",
    "data modeling", "data cleaning", "data enrichment", "data quality controls",
    "data quality frameworks", "data quality monitoring", "data reconciliation",
    "data analysis", "data center infrastructure", "database architecture",
    "database capacity planning", "database performance assessment", "database security",
    "deduplication", "disaster recovery", "distributed data processing",
    "distributed data storage", "failure recovery", "fault-tolerant pipelines",
    "high availability", "large-scale data processing", "large-scale databases",
    "monitoring", "monitoring and alerting", "performance optimization",
    "production deployment", "query optimization", "real-time data pipelines",
    "real-time pipelines", "scheduled integration", "scheduled jobs", "security architecture",
    "security compliance", "security controls", "system integration", "system integration flow",
    "test case design", "test result analysis", "test specification design",
    "test strategy development", "testing", "time series modeling", "troubleshooting",
    "virtualization", "workflow automation", "workflow scheduling", "cloud architecture",
    "cloud deployment", "cloud resource management", "cloud service provisioning",
    "cybersecurity", "mobile app development", "computer networking", "containers",
    "deep learning pipelines", "production deployment", "classification", "deep learning",
    "machine learning", "streaming", "batch processing", "backup and recovery",
    "api integration", "api integrations", "api testing", "bi reporting", "bi visualization",
    "change control", "cloud resource management", "cloud service provisioning",
    "large-scale data processing", "load testing", "manual testing", "monitoring and alerting",
    "query optimization", "reporting tools", "security compliance", "sql scripts",
    "sql troubleshooting", "time series preprocessing", "vector databases", "anomaly detection",
}

LABEL_OVERRIDES = {norm(key): value for key, value in LABEL_OVERRIDES.items()}
METHOD_LABEL_KEYS = {norm(key) for key in METHOD_LABEL_KEYS}

CANONICAL_REPAIRS = {
    ("2141955", "airflowdagorchestration"): "Airflow",
    ("2141955", "dataqualityframeworks"): "data quality monitoring",
    ("2141955", "datatransformations"): "data transformation",
    ("2141955", "ragpipelines"): "RAG pipeline",
    ("2139328", "backupandrecovery"): "disaster recovery",
    ("2139328", "databasecapacityplanning"): "database capacity assessment",
    ("2143923", "sqltroubleshooting"): "troubleshooting",
    ("2143927", "sqltroubleshooting"): "troubleshooting",
    ("2144686", "deeplearningpipelines"): "machine/deep-learning pipelines",
    ("2144686", "monitoring"): "monitoring",
    ("2144686", "productiondeployment"): "deployment",
    ("2144686", "systemintegration"): "model integration",
    ("2139159", "testcasedesign"): "test specification design",
    ("2144784", "dataqualitycontrols"): "quality control",
    ("2139603", "testresultanalysis"): "test result recording",
}

EXTRA_DECISIONS = {
    "nosqlproducts": ("approve_positive", "database or query technology", "NoSQL is a database technology named in the requirements.", "high"),
    "sqlqueries": ("approve_positive", "database or query technology", "SQL queries are a concrete query technology used in responsibilities.", "high"),
    "systemarchitecture": ("approve_positive", "technical method, protocol, or architecture", "Architecture is explicitly technical and named in the source.", "high"),
    "cosodulieuquymolon": ("approve_positive", "database or query technology", "The source explicitly requires knowledge of large-scale databases.", "medium"),
    "etltool": ("repair_positive", "technical method, protocol, or architecture", "ETL is the technical method named in this tool phrase.", "medium"),
    "scheduled": ("approve_positive", "technical method, protocol, or architecture", "Scheduled integration is listed as an integration pattern.", "medium"),
    "kientruc": ("approve_positive", "technical method, protocol, or architecture", "The source refers to technical architecture solutions.", "medium"),
    "bigdatastreamingprocessing": ("split_positive", "cloud or data platform", "The source combines two technical concepts; split into Big Data and Streaming Processing spans.", "medium"),
    "trungtamdulieu": ("approve_positive", "cloud or data platform", "Data center is a technical infrastructure/platform concept in the source.", "medium"),
    "aohoa": ("approve_positive", "technical method, protocol, or architecture", "Virtualization is explicitly listed as a technical capability.", "high"),
    "backend": ("reject_background", "", "This is a team/role reference, not a technical entity span.", "high"),
    "dataanalyst": ("reject_background", "", "This is a job role/team reference, not a technical entity span.", "high"),
    "amazon": ("reject_background", "", "This is only a subspan of the product name Amazon Bedrock.", "high"),
    "ngonngukhac": ("out_of_scope", "", "This is a generic spoken-language reference; the current six labels have no natural-language category.", "high"),
    "prd": ("out_of_scope", "", "PRD is a project document/process artifact, outside the current technical entity labels.", "high"),
    "b2bsaas": ("out_of_scope", "", "This describes a business/product model, not a technical skill entity.", "high"),
    "dashboardtemplates": ("reject_background", "", "This is a generic deliverable, not a named tool or technical method.", "high"),
    "reusableframeworks": ("reject_background", "", "This is a generic capability phrase, not a named framework/library.", "high"),
    "tbp": ("out_of_scope", "", "Vietnamese abbreviation for a department head in this context, not a technical entity.", "high"),
    "mbbank": ("out_of_scope", "", "Employer/company name, outside the skill label scope.", "high"),
    "phantichdulieu": ("reject_background", "", "Here it names a team/group in the responsibility sentence, not a skill span.", "medium"),
    "phanmem": ("reject_background", "", "Generic word for software, not a specific technology or method.", "high"),
}


def direct_label(skill: str, proposed: str) -> tuple[str, str, str] | None:
    key = norm(skill)
    override = LABEL_OVERRIDES.get(key)
    if override:
        label, rationale, confidence = override
        if label:
            return label, confidence, rationale
        return None
    if key in METHOD_LABEL_KEYS:
        return "technical method, protocol, or architecture", "medium", "A technical practice or architecture concept in the source context."
    if key in {"python", "java", "javascript", "typescript", "scala", "golang", "rust", "csharp", "cplusplus", "php", "ruby", "kotlin", "swift", "bash"}:
        return "programming language", "high", "Known programming language; taxonomy overrides the model suggestion."
    if key in {"sql", "mysql", "postgresql", "postgres", "rdbms", "nosql", "nosqlproducts", "oracle", "mongodb", "redis", "cassandra", "elasticsearch", "opensearch", "sqlqueries", "sqlscripts", "sqlwindowfunctions", "vectordatabase", "vectordatabases", "graphdatabases", "relationaldatabases", "databasetechnology", "databasearchitecture", "databasesecurity", "databasevault", "queryoptimization", "queryoptimisation", "executionplans", "sqlserver", "starrocks"}:
        return "database or query technology", "high", "Named database/query technology; taxonomy overrides the model suggestion."
    if key in {"pytorch", "tensorflow", "react", "spring", "django", "flask", "fastapi", "scikitlearn", "numpy", "pandas", "dbt"}:
        label = "software development or testing tool" if key == "dbt" else "software framework or library"
        return label, "high", "Known framework/library or data-development tool."
    if key in {"aws", "awslambda", "awss3", "s3", "lambda", "azure", "gcp", "airflow", "apacheairflow", "dagster", "snowflake", "bigquery", "databricks", "hadoop", "spark", "kafka", "flink", "bigdata", "ibmbigdata", "datacenterinfrastructure", "datacenter", "trungtamdulieu", "cloud", "cloudarchitecture", "cloudplatform", "cloudserviceprovisioning", "cloudresourcemanagement", "kubernetes", "openstack", "vmware"}:
        return "cloud or data platform", "high", "Named cloud/data platform or infrastructure technology."
    if key in {"git", "github", "selenium", "cucumber", "postman", "jenkins", "docker", "terraform", "jira", "tableau", "powerbi", "cursor", "claudecode", "githubcopilot"}:
        return "software development or testing tool", "high", "Named software development/testing tool."
    method_tokens = ("etl", "elt", "cicd", "api", "rest", "architecture", "integration", "testing", "testcase", "teststrategy", "testspecification", "backup", "recovery", "migration", "validation", "transformation", "processing", "monitoring", "alerting", "optimization", "optimisation", "modeling", "modelling", "workflow", "timeseries", "anomalydetection", "datacleaning", "dataquality", "dataanalysis", "dataenrichment", "datastandardization", "dataintegration", "reconciliation", "virtualization", "aoh oa")
    if any(token in key for token in method_tokens):
        return "technical method, protocol, or architecture", "medium", "Technical process/method inferred from the term and context."
    if proposed in LABELS:
        if key in {"sql", "dbt", "english", "japanese", "notion", "slack", "claude", "gemini"}:
            return None
        return proposed, "medium", "Kept the GLiNER proposal after checking the term against the six-label scope."
    # Conservative fallback for explicit class words.
    if "database" in key or "query" in key or "rdbms" in key:
        return "database or query technology", "medium", "Term explicitly names a database/query concept."
    if "framework" in key or "library" in key:
        return "software framework or library", "medium", "Term explicitly names a framework/library concept."
    if "tool" in key:
        return "software development or testing tool", "low", "Generic tool term; retained as a weak first-pass label."
    return None


def main() -> None:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    jobs = {str(job["id"]): job for job in raw["jobs"]}
    rows = list(csv.DictReader(QUEUE_PATH.open(encoding="utf-8-sig", newline="")))
    output: list[dict[str, Any]] = []
    positive = 0
    needs_span = 0
    excluded = 0

    for row in rows:
        item = dict(row)
        item.update({
            "reviewer": "Codex AI first-pass",
            "ai_decision": "",
            "ai_approved_skill": "",
            "ai_approved_surface": "",
            "ai_approved_section": "",
            "ai_approved_gliner_label": "",
            "ai_review_confidence": "",
            "ai_review_rationale": "",
        })
        jid = row["job_id"]
        skill = row["candidate_skill"]
        kind = row["candidate_kind"]
        raw_job = jobs[jid]
        source_surface = row["source_surface"]
        section = row["source_section"]
        surface = source_surface
        repair = REPAIRS.get((jid, norm(skill)))

        if kind == "model_extra_candidate":
            decision = EXTRA_DECISIONS.get(norm(skill))
            if decision is None:
                item["ai_decision"] = "needs_review"
                item["ai_review_rationale"] = "Không có quyết định chắc chắn theo rubric; không đưa vào train."
                output.append(item)
                continue
            action, label, rationale, confidence = decision
            if action == "split_positive":
                for part, part_label in (("Big Data", "cloud or data platform"), ("Streaming Processing", "technical method, protocol, or architecture")):
                    part_row = dict(item)
                    source_text = raw_job.get(section + "_text") or ""
                    matches = exact_occurrences(source_text, part)
                    if matches:
                        start, end, actual = matches[0]
                        part_row.update({
                            "candidate_id": row["candidate_id"] + ("-BD" if part == "Big Data" else "-SP"),
                            "ai_decision": "approve_positive",
                            "ai_approved_skill": part,
                            "ai_approved_surface": actual,
                            "ai_approved_section": section,
                            "span_start_char": start,
                            "span_end_char_exclusive": end,
                            "ai_approved_gliner_label": part_label,
                            "ai_review_confidence": "medium",
                            "ai_review_rationale": rationale,
                        })
                        positive += 1
                        output.append(part_row)
                continue
            if decision[0] in {"approve_positive", "repair_positive"} and kind == "model_extra_candidate":
                if norm(skill) == "etltool":
                    surface = "ETL"
                    skill = "ETL"
                    label = "technical method, protocol, or architecture"
                    action = "repair_positive"
                source_text = raw_job.get(section + "_text") or ""
                match = matching_source_span(row, source_text, surface)
                if not match:
                    item["ai_decision"] = "needs_span"
                    item["ai_review_rationale"] = "Ứng viên có vẻ là skill nhưng không xác minh được span chính xác; loại khỏi train pilot."
                    needs_span += 1
                    output.append(item)
                    continue
                start, end, actual = match
                item.update({
                    "ai_decision": action,
                    "ai_approved_skill": skill,
                    "ai_approved_surface": actual,
                    "ai_approved_section": section,
                    "span_start_char": start,
                    "span_end_char_exclusive": end,
                    "ai_approved_gliner_label": label,
                    "ai_review_confidence": confidence,
                    "ai_review_rationale": rationale,
                })
                positive += 1
            else:
                item["ai_decision"] = "out_of_scope" if action == "out_of_scope" else "reject_background"
                item["ai_review_confidence"] = confidence
                item["ai_review_rationale"] = rationale
                excluded += 1
            output.append(item)
            continue

        if surface:
            source_text = raw_job.get(section + "_text") or ""
            match = matching_source_span(row, source_text, surface)
            if match:
                start, end, surface = match
                item["span_start_char"] = start
                item["span_end_char_exclusive"] = end
            else:
                surface = ""

        if not surface and repair:
            repair_section, repair_surface = repair
            source_text = raw_job.get(repair_section + "_text") or ""
            match = matching_source_span({}, source_text, repair_surface)
            if match:
                section = repair_section
                start, end, surface = match
                item["span_start_char"] = start
                item["span_end_char_exclusive"] = end
                item["ai_review_confidence"] = "medium"
            else:
                surface = ""

        if not surface:
            out_of_scope = LABEL_OVERRIDES.get(norm(skill))
            if out_of_scope and not out_of_scope[0]:
                item.update({
                    "ai_decision": "out_of_scope",
                    "ai_review_confidence": out_of_scope[2],
                    "ai_review_rationale": out_of_scope[1],
                })
                excluded += 1
                output.append(item)
                continue
            item["ai_decision"] = "needs_span"
            item["ai_review_confidence"] = "low"
            item["ai_review_rationale"] = "Không tìm thấy cụm/alias đủ chắc trong mô tả; không gán span giả, loại khỏi train pilot."
            needs_span += 1
            output.append(item)
            continue

        proposed = row["proposed_gliner_label"].split(" | ")[0].strip()
        source_text = raw_job.get(section + "_text") or ""
        if norm(skill) == "bi":
            if is_bi_team_mention(source_text, start, end):
                item.update({
                    "ai_decision": "reject_background",
                    "ai_approved_surface": surface,
                    "ai_approved_section": section,
                    "ai_review_confidence": "high",
                    "ai_review_rationale": "BI is listed as a collaborating team between Backend and Data Analyst, not as a skill mention.",
                })
                excluded += 1
                output.append(item)
                continue
        chosen = direct_label(skill, proposed)
        if chosen is None:
            override = LABEL_OVERRIDES.get(norm(skill))
            if override and not override[0]:
                item.update({
                    "ai_decision": "out_of_scope",
                    "ai_approved_surface": surface,
                    "ai_approved_section": section,
                    "ai_review_confidence": override[2],
                    "ai_review_rationale": override[1],
                })
                excluded += 1
                output.append(item)
                continue
            item["ai_decision"] = "needs_label"
            item["ai_approved_surface"] = surface
            item["ai_approved_section"] = section
            item["ai_review_confidence"] = "low"
            item["ai_review_rationale"] = "Đã định vị được cụm nhưng chưa đủ chắc để chọn một trong sáu nhãn; loại khỏi train pilot."
            output.append(item)
            continue

        label, confidence, rationale = chosen
        approved_skill = CANONICAL_REPAIRS.get((jid, norm(skill)), skill)
        item.update({
            "ai_decision": "repair_positive" if surface != source_surface else "approve_positive",
            "ai_approved_skill": approved_skill,
            "ai_approved_surface": surface,
            "ai_approved_section": section,
            "ai_approved_gliner_label": label,
            "ai_review_confidence": confidence,
            "ai_review_rationale": rationale,
        })
        positive += 1
        output.append(item)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = list(output[0]) if output else []
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    print(f"AI-reviewed rows: {len(output)}")
    print(f"positive/repaired: {positive}; needs span: {needs_span}; excluded: {excluded}")
    from collections import Counter
    print("decisions:", dict(Counter(row["ai_decision"] for row in output)))
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
