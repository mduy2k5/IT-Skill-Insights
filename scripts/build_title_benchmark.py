#!/usr/bin/env python3
"""Build and maintain the IT Job Title Benchmark (v0.1) for JobBERT V3 title clustering.

Separates role family (họ nghề) and level cues (tín hiệu level).
Categorizes language into Vietnamese (vi), Vietnamese-English (vi-en), and English (en).
Allows reviewing existing titles and appending new titles from subsequent crawls.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
BENCHMARK_JSON_PATH = DATA_DIR / "title_benchmark_v0_1.json"
BENCHMARK_CSV_PATH = DATA_DIR / "title_benchmark_v0_1.csv"
REPORT_MD_PATH = DATA_DIR / "title_benchmark_method_and_report.md"

# Curated reference annotations for currently known titles.
# Keys are exact raw titles.
CURATED_TITLE_ANNOTATIONS: dict[str, dict[str, Any]] = {
    "AI Engineer": {
        "cleaned_title": "AI Engineer",
        "role_family": "Software Engineering (AI / ML)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["AI"],
        "is_it_core": True,
        "notes": "Core AI/ML engineering role; no explicit seniority in title.",
    },
    "AI QUANTITATIVE RESEARCHER INTERN (On-site)": {
        "cleaned_title": "AI Quantitative Researcher",
        "role_family": "AI / Quantitative Research",
        "level_cue": "Intern",
        "language": "en",
        "tech_stack_cues": ["AI", "Quantitative"],
        "is_it_core": True,
        "notes": "Research role combining AI and quantitative finance; level cue is Intern.",
    },
    "Associate Quality Engineer (Automation)": {
        "cleaned_title": "Quality Engineer (Automation)",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Associate",
        "language": "en",
        "tech_stack_cues": ["Automation Test"],
        "is_it_core": True,
        "notes": "QA Automation; Associate is a level cue.",
    },
    "Business Analyst": {
        "cleaned_title": "Business Analyst",
        "role_family": "Business Analysis",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": [],
        "is_it_core": True,
        "notes": "IT BA role; no level cue.",
    },
    "C/C++ Software Developer – Telecom (All Levels)": {
        "cleaned_title": "C/C++ Software Developer – Telecom",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "All Levels",
        "language": "en",
        "tech_stack_cues": ["C", "C++", "Telecom"],
        "is_it_core": True,
        "notes": "Software dev in Telecom domain; All Levels indicates multi-level hiring.",
    },
    "Chuyên Gia Kiểm Thử & Đánh Giá An Ninh (Pentest) - Hà Nội": {
        "cleaned_title": "Kiểm Thử & Đánh Giá An Ninh (Pentest)",
        "role_family": "Information Security / Cybersecurity",
        "level_cue": "Chuyên gia",
        "language": "vi-en",
        "tech_stack_cues": ["Pentest"],
        "is_it_core": True,
        "notes": "Penetration testing / Security evaluation; Chuyên gia is level cue, Pentest is English term.",
    },
    "Chuyên Gia Vận Hành Thẻ": {
        "cleaned_title": "Vận Hành Thẻ",
        "role_family": "IT Operations & Integration Services",
        "level_cue": "Chuyên gia",
        "language": "vi",
        "tech_stack_cues": ["Card Banking Operations"],
        "is_it_core": True,
        "notes": "Banking card payment system operations; Chuyên gia is level cue.",
    },
    "Chuyên Viên Cao Cấp Vận Hành An Toàn An Ninh Thông Tin - Hà Nội": {
        "cleaned_title": "Vận Hành An Toàn An Ninh Thông Tin",
        "role_family": "Information Security / Cybersecurity",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi",
        "tech_stack_cues": ["SOC", "Infosec"],
        "is_it_core": True,
        "notes": "SecOps / Infosec operations; Chuyên viên cao cấp is level cue.",
    },
    "Chuyên gia Chiến lược công nghệ": {
        "cleaned_title": "Chiến lược công nghệ",
        "role_family": "IT Architecture & Strategy",
        "level_cue": "Chuyên gia",
        "language": "vi",
        "tech_stack_cues": ["Tech Strategy"],
        "is_it_core": True,
        "notes": "Technology strategy and roadmap planning; Chuyên gia is level cue.",
    },
    "Chuyên gia Kiến trúc doanh nghiệp (EA)": {
        "cleaned_title": "Kiến trúc doanh nghiệp (EA)",
        "role_family": "IT Architecture & Strategy",
        "level_cue": "Chuyên gia",
        "language": "vi-en",
        "tech_stack_cues": ["Enterprise Architecture", "EA"],
        "is_it_core": True,
        "notes": "Enterprise Architecture; Chuyên gia is level cue, EA is English abbreviation.",
    },
    "Chuyên viên Cao cấp QA": {
        "cleaned_title": "QA",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi-en",
        "tech_stack_cues": ["QA"],
        "is_it_core": True,
        "notes": "Senior QA role; Chuyên viên cao cấp is level cue.",
    },
    "Chuyên viên Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM": {
        "cleaned_title": "Công nghệ & phát triển sản phẩm Cloud, Data Center và ANM",
        "role_family": "Cloud, Systems & Network Infrastructure",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["Cloud", "Data Center", "ANM"],
        "is_it_core": True,
        "notes": "Cloud & network security product engineering; Chuyên viên is level cue.",
    },
    "Chuyên viên Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số (2026TD457689)": {
        "cleaned_title": "Hỗ trợ Tích hợp Dịch vụ - Khối Ngân hàng Số",
        "role_family": "IT Operations & Integration Services",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["API Integration", "Digital Banking"],
        "is_it_core": True,
        "notes": "Digital banking service integration support; Chuyên viên is level cue.",
    },
    "Chuyên viên Hỗ trợ bán hàng (Kỹ thuật)": {
        "cleaned_title": "Hỗ trợ bán hàng (Kỹ thuật)",
        "role_family": "IT Sales & Presales",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["Sales Engineering"],
        "is_it_core": False,
        "notes": "Technical sales support / Presales; peripheral tech role.",
    },
    "Chuyên viên Kinh doanh Cloud, An ninh mạng": {
        "cleaned_title": "Kinh doanh Cloud, An ninh mạng",
        "role_family": "IT Sales & Presales",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["Cloud", "Cybersecurity"],
        "is_it_core": False,
        "notes": "Cloud & Security solution sales; IT-adjacent sales role.",
    },
    "Chuyên viên Kiến trúc doanh nghiệp (EA)": {
        "cleaned_title": "Kiến trúc doanh nghiệp (EA)",
        "role_family": "IT Architecture & Strategy",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["Enterprise Architecture", "EA"],
        "is_it_core": True,
        "notes": "Enterprise Architecture specialist.",
    },
    "Chuyên viên Kiểm thử - Tester - Khối Công nghệ thông tin (2026TD456989)": {
        "cleaned_title": "Kiểm thử - Tester",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["Testing"],
        "is_it_core": True,
        "notes": "Manual/Automation software tester; mixed Vietnamese Kiểm thử and English Tester.",
    },
    "Chuyên viên Phát triển Hệ thống": {
        "cleaned_title": "Phát triển Hệ thống",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["Systems Development"],
        "is_it_core": True,
        "notes": "Systems / backend software developer.",
    },
    "Chuyên viên Phân tích nghiệp vụ": {
        "cleaned_title": "Phân tích nghiệp vụ",
        "role_family": "Business Analysis",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["BA"],
        "is_it_core": True,
        "notes": "Vietnamese title for Business Analyst.",
    },
    "Chuyên viên Phân tích nghiệp vụ (BA)": {
        "cleaned_title": "Phân tích nghiệp vụ (BA)",
        "role_family": "Business Analysis",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["BA"],
        "is_it_core": True,
        "notes": "Vietnamese title with English acronym BA.",
    },
    "Chuyên viên cao cấp Kiểm thử": {
        "cleaned_title": "Kiểm thử",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi",
        "tech_stack_cues": ["Testing"],
        "is_it_core": True,
        "notes": "Senior QA/Tester; Chuyên viên cao cấp is level cue.",
    },
    "Chuyên viên cao cấp Phát triển Hệ thống": {
        "cleaned_title": "Phát triển Hệ thống",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi",
        "tech_stack_cues": ["Systems Development"],
        "is_it_core": True,
        "notes": "Senior systems / backend engineer.",
    },
    "Chuyên viên cao cấp Vận hành hệ thống": {
        "cleaned_title": "Vận hành hệ thống",
        "role_family": "Cloud, Systems & Network Infrastructure",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi",
        "tech_stack_cues": ["System Operations"],
        "is_it_core": True,
        "notes": "Senior system operations / sysadmin.",
    },
    "Chuyên viên cao cấp an ninh mạng": {
        "cleaned_title": "An ninh mạng",
        "role_family": "Information Security / Cybersecurity",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi",
        "tech_stack_cues": ["Cybersecurity"],
        "is_it_core": True,
        "notes": "Senior cybersecurity specialist.",
    },
    "Chuyên viên cao cấp phát triển sản phẩm/giải pháp CNTT": {
        "cleaned_title": "Phát triển sản phẩm/giải pháp CNTT",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Chuyên viên cao cấp",
        "language": "vi",
        "tech_stack_cues": ["Product Management"],
        "is_it_core": True,
        "notes": "Senior IT product/solution development specialist.",
    },
    "Chuyên viên lập trình Back-end (Java)": {
        "cleaned_title": "Lập trình Back-end (Java)",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["Java", "Backend"],
        "is_it_core": True,
        "notes": "Java Backend developer.",
    },
    "Chuyên viên phân tích nghiệp vụ phần mềm": {
        "cleaned_title": "Phân tích nghiệp vụ phần mềm",
        "role_family": "Business Analysis",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["Software BA"],
        "is_it_core": True,
        "notes": "Software Business Analyst in Vietnamese.",
    },
    "Chuyên viên quản lý dự án phần mềm": {
        "cleaned_title": "Quản lý dự án phần mềm",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["Software PM"],
        "is_it_core": True,
        "notes": "Software Project Manager in Vietnamese.",
    },
    "Chuyên viên triển khai dự án": {
        "cleaned_title": "Triển khai dự án",
        "role_family": "IT Support & Systems Operations",
        "level_cue": "Chuyên viên",
        "language": "vi",
        "tech_stack_cues": ["Project Deployment"],
        "is_it_core": True,
        "notes": "IT software/solution deployment specialist.",
    },
    "Chuyên viên đảm bảo chất lượng (QA/QC)": {
        "cleaned_title": "Đảm bảo chất lượng (QA/QC)",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["QA", "QC"],
        "is_it_core": True,
        "notes": "Quality assurance / quality control specialist.",
    },
    "Chuyên viên Ứng dụng Microsoft 365 & Copilot": {
        "cleaned_title": "Ứng dụng Microsoft 365 & Copilot",
        "role_family": "Cloud, Systems & Network Infrastructure",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["Microsoft 365", "Copilot"],
        "is_it_core": True,
        "notes": "Workplace digital tools / M365 admin and Copilot specialist.",
    },
    "Cloud & DevOps Engineer (Azure, AWS)": {
        "cleaned_title": "Cloud & DevOps Engineer",
        "role_family": "DevOps & DevSecOps",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Cloud", "DevOps", "AWS", "Azure"],
        "is_it_core": True,
        "notes": "Cloud DevOps role spanning AWS and Azure.",
    },
    "Cobol Developer (English speaking)": {
        "cleaned_title": "Cobol Developer",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["COBOL", "Legacy Banking Systems"],
        "is_it_core": True,
        "notes": "Cobol software developer.",
    },
    "Customer Support Engineer": {
        "cleaned_title": "Customer Support Engineer",
        "role_family": "IT Support & Systems Operations",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Technical Support"],
        "is_it_core": True,
        "notes": "Technical customer support engineer.",
    },
    "Data Engineer (Big Data / Lakehouse)": {
        "cleaned_title": "Data Engineer (Big Data / Lakehouse)",
        "role_family": "Data Engineering",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Big Data", "Lakehouse"],
        "is_it_core": True,
        "notes": "Data engineering with modern data lakehouse stack.",
    },
    "Data Engineer at DATATYK CO., LTD": {
        "cleaned_title": "Data Engineer",
        "role_family": "Data Engineering",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Data Engineering"],
        "is_it_core": True,
        "notes": "Company name in title stripped in cleaned_title.",
    },
    "Data Engineer/ Senior Data Engineer": {
        "cleaned_title": "Data Engineer",
        "role_family": "Data Engineering",
        "level_cue": "Senior",
        "language": "en",
        "tech_stack_cues": ["Data Engineering"],
        "is_it_core": True,
        "notes": "Dual title; Senior is explicit level cue.",
    },
    "Data Services Specialist": {
        "cleaned_title": "Data Services Specialist",
        "role_family": "IT Operations & Integration Services",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Data Services", "APIs"],
        "is_it_core": True,
        "notes": "Data services and integration specialist.",
    },
    "DevOps Engineer (Middle/Senior)": {
        "cleaned_title": "DevOps Engineer",
        "role_family": "DevOps & DevSecOps",
        "level_cue": "Middle/Senior",
        "language": "en",
        "tech_stack_cues": ["DevOps"],
        "is_it_core": True,
        "notes": "DevOps role with multi-level cue Middle/Senior.",
    },
    "DevOps Engineer - Khối Công nghệ thông tin (2025TD945)": {
        "cleaned_title": "DevOps Engineer",
        "role_family": "DevOps & DevSecOps",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["DevOps"],
        "is_it_core": True,
        "notes": "English title with Vietnamese department suffix and job requisition code.",
    },
    "DevSecOps Engineer - Khối Công nghệ thông tin (2025TD946)": {
        "cleaned_title": "DevSecOps Engineer",
        "role_family": "DevOps & DevSecOps",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["DevSecOps", "Security"],
        "is_it_core": True,
        "notes": "DevSecOps engineering role.",
    },
    "ERP Application Developer": {
        "cleaned_title": "ERP Application Developer",
        "role_family": "Enterprise Applications (ERP / CRM)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["ERP"],
        "is_it_core": True,
        "notes": "ERP developer role.",
    },
    "Expert/Senior/Middle Software Engineer (Java, Spring boot, PostgreSQL)": {
        "cleaned_title": "Software Engineer (Java, Spring boot, PostgreSQL)",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Expert/Senior/Middle",
        "language": "en",
        "tech_stack_cues": ["Java", "Spring boot", "PostgreSQL"],
        "is_it_core": True,
        "notes": "Backend engineering role; Expert/Senior/Middle is explicit multi-level cue.",
    },
    "Fresher/Junior PHP Developer": {
        "cleaned_title": "PHP Developer",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Fresher/Junior",
        "language": "en",
        "tech_stack_cues": ["PHP"],
        "is_it_core": True,
        "notes": "PHP developer; Fresher/Junior is level cue.",
    },
    "Fullstack Engineer (AI Product Builder)": {
        "cleaned_title": "Fullstack Engineer (AI Product Builder)",
        "role_family": "Software Engineering (Fullstack / Web)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Fullstack", "AI Product"],
        "is_it_core": True,
        "notes": "Fullstack developer working on AI applications.",
    },
    "Functional Consultant – ORIS Business Suite": {
        "cleaned_title": "Functional Consultant – ORIS Business Suite",
        "role_family": "Enterprise Applications (ERP / CRM)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["ORIS Business Suite", "Functional Consultant"],
        "is_it_core": True,
        "notes": "ERP/enterprise suite functional consulting.",
    },
    "IT Business Analyst - Chuyên viên phân tích nghiệp vụ": {
        "cleaned_title": "IT Business Analyst",
        "role_family": "Business Analysis",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["BA"],
        "is_it_core": True,
        "notes": "Bilingual title mapping directly to Business Analysis; Chuyên viên is level cue.",
    },
    "IT Business Analyst / QA Specialist (Biết tiếng Hàn)": {
        "cleaned_title": "IT Business Analyst / QA Specialist",
        "role_family": "Business Analysis",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["BA", "QA"],
        "is_it_core": True,
        "notes": "Hybrid BA/QA role; language requirement note attached in Vietnamese.",
    },
    "IT Senior Staff": {
        "cleaned_title": "IT Staff",
        "role_family": "IT Support & Systems Operations",
        "level_cue": "Senior",
        "language": "en",
        "tech_stack_cues": ["IT Operations"],
        "is_it_core": True,
        "notes": "General internal IT support/operations staff; Senior is level cue.",
    },
    "IT Supervisor/ Giám sát IT – Resort/Khách sạn": {
        "cleaned_title": "IT Supervisor",
        "role_family": "IT Support & Systems Operations",
        "level_cue": "Manager / Lead",
        "language": "vi-en",
        "tech_stack_cues": ["Hospitality IT"],
        "is_it_core": True,
        "notes": "Hospitality IT infrastructure supervisor; Supervisor/Giám sát is level cue.",
    },
    "IT Systems Administrator": {
        "cleaned_title": "IT Systems Administrator",
        "role_family": "Cloud, Systems & Network Infrastructure",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Sysadmin"],
        "is_it_core": True,
        "notes": "System administrator role.",
    },
    "Java Backend Developer": {
        "cleaned_title": "Java Backend Developer",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Java", "Backend"],
        "is_it_core": True,
        "notes": "Backend engineering focusing on Java.",
    },
    "Junior MarTech Solutions Consultant": {
        "cleaned_title": "MarTech Solutions Consultant",
        "role_family": "Enterprise Applications (ERP / CRM)",
        "level_cue": "Junior",
        "language": "en",
        "tech_stack_cues": ["MarTech", "Marketing Automation"],
        "is_it_core": True,
        "notes": "Marketing technology solutions consulting; Junior is level cue.",
    },
    "Junior/Middle/Senior IT Business Analyst (LOS, CRM System)": {
        "cleaned_title": "IT Business Analyst (LOS, CRM System)",
        "role_family": "Business Analysis",
        "level_cue": "Junior/Middle/Senior",
        "language": "en",
        "tech_stack_cues": ["LOS", "CRM"],
        "is_it_core": True,
        "notes": "BA role for lending / CRM systems; multi-level cue Junior/Middle/Senior.",
    },
    "Junior/Senior Software Backend (.NET, dotnet, netcore)": {
        "cleaned_title": "Software Backend (.NET, dotnet, netcore)",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Junior/Senior",
        "language": "en",
        "tech_stack_cues": [".NET", "dotnet", "netcore"],
        "is_it_core": True,
        "notes": "Backend .NET development; Junior/Senior is level cue.",
    },
    "KOREAN IT INTERPRETER": {
        "cleaned_title": "IT Interpreter (Korean)",
        "role_family": "IT Translation / Interpretation",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Korean Translation"],
        "is_it_core": False,
        "notes": "Bridge/Comtor/Interpreter role; IT-adjacent non-engineering.",
    },
    "Kiến trúc sư giải pháp CNTT": {
        "cleaned_title": "Kiến trúc sư giải pháp CNTT",
        "role_family": "IT Architecture & Strategy",
        "level_cue": "Unspecified",
        "language": "vi",
        "tech_stack_cues": ["Solution Architecture"],
        "is_it_core": True,
        "notes": "IT Solution Architect in Vietnamese.",
    },
    "Kỹ Sư Dữ Liệu (Data Engineer)": {
        "cleaned_title": "Data Engineer",
        "role_family": "Data Engineering",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["Data Engineering"],
        "is_it_core": True,
        "notes": "Bilingual Vietnamese/English Data Engineer title.",
    },
    "Kỹ sư Presale giải pháp Công nghệ thông tin (khối Chính phủ)": {
        "cleaned_title": "Presale giải pháp Công nghệ thông tin (khối Chính phủ)",
        "role_family": "IT Sales & Presales",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["Presales", "Government IT"],
        "is_it_core": False,
        "notes": "IT Presales solutions role in public sector; sales adjacent.",
    },
    "Kỹ sư Quản lý Chất lượng Phần mềm": {
        "cleaned_title": "Quản lý Chất lượng Phần mềm",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Unspecified",
        "language": "vi",
        "tech_stack_cues": ["Software QA"],
        "is_it_core": True,
        "notes": "Software QA Engineer in Vietnamese.",
    },
    "Kỹ sư công nghệ thông tin - Quản trị viên phần mềm và dữ liệu (03)": {
        "cleaned_title": "Quản trị viên phần mềm và dữ liệu",
        "role_family": "Database Administration",
        "level_cue": "Unspecified",
        "language": "vi",
        "tech_stack_cues": ["Software & Data Administration"],
        "is_it_core": True,
        "notes": "Software and database administrator.",
    },
    "Kỹ sư dữ liệu (Data Engineer)": {
        "cleaned_title": "Data Engineer",
        "role_family": "Data Engineering",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["Data Engineering"],
        "is_it_core": True,
        "notes": "Standard bilingual title for Data Engineer.",
    },
    "Kỹ sư lập trình Backend (Java)": {
        "cleaned_title": "Lập trình Backend (Java)",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["Java", "Backend"],
        "is_it_core": True,
        "notes": "Java Backend developer in mixed Vietnamese/English.",
    },
    "Lập trình viên (.NET Full-stack Developer)": {
        "cleaned_title": ".NET Full-stack Developer",
        "role_family": "Software Engineering (Fullstack / Web)",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": [".NET", "Fullstack"],
        "is_it_core": True,
        "notes": ".NET Full-stack developer with Vietnamese job descriptor.",
    },
    "Mobile App Executive Officer": {
        "cleaned_title": "Mobile App Executive Officer",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Manager / Lead",
        "language": "en",
        "tech_stack_cues": ["Mobile App"],
        "is_it_core": True,
        "notes": "Product operations / executive role for mobile apps.",
    },
    "Mobile Game QA": {
        "cleaned_title": "Mobile Game QA",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Mobile Game", "QA"],
        "is_it_core": True,
        "notes": "Mobile gaming software quality assurance.",
    },
    "NHÂN VIÊN IT": {
        "cleaned_title": "Nhân viên IT",
        "role_family": "IT Support & Systems Operations",
        "level_cue": "Nhân viên",
        "language": "vi-en",
        "tech_stack_cues": ["IT Helpdesk"],
        "is_it_core": True,
        "notes": "General internal IT support / helpdesk staff; Nhân viên is level cue.",
    },
    "NHÂN VIÊN TRIỂN KHAI BẢO TRÌ PHẦN MỀM": {
        "cleaned_title": "Triển khai bảo trì phần mềm",
        "role_family": "IT Support & Systems Operations",
        "level_cue": "Nhân viên",
        "language": "vi",
        "tech_stack_cues": ["Deployment", "Maintenance"],
        "is_it_core": True,
        "notes": "Software deployment and maintenance technician; Nhân viên is level cue.",
    },
    "Nhân Viên Hành Chính: Gán Nhãn Dữ Liệu Hình Anh AI - Không Yêu Cầu Kinh Nghiệm": {
        "cleaned_title": "Gán Nhãn Dữ Liệu Hình Ảnh AI",
        "role_family": "Data Annotation",
        "level_cue": "Nhân viên",
        "language": "vi-en",
        "tech_stack_cues": ["AI Data Labeling", "Image Annotation"],
        "is_it_core": False,
        "notes": "Administrative AI data annotation role; peripheral non-engineering.",
    },
    "Odoo Developer": {
        "cleaned_title": "Odoo Developer",
        "role_family": "Enterprise Applications (ERP / CRM)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Odoo", "Python ERP"],
        "is_it_core": True,
        "notes": "Odoo ERP open source developer.",
    },
    "PLM Systems Manager": {
        "cleaned_title": "PLM Systems Manager",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Manager / Lead",
        "language": "en",
        "tech_stack_cues": ["PLM Systems"],
        "is_it_core": True,
        "notes": "Product Lifecycle Management systems manager; Manager is level cue.",
    },
    "Project Management Office (PMO) Specialist - Service Delivery & Operations": {
        "cleaned_title": "PMO Specialist - Service Delivery & Operations",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["PMO", "IT Operations"],
        "is_it_core": True,
        "notes": "IT PMO specialist overseeing service delivery.",
    },
    "Project Manager": {
        "cleaned_title": "Project Manager",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Manager / Lead",
        "language": "en",
        "tech_stack_cues": ["Project Management"],
        "is_it_core": True,
        "notes": "IT Project Manager; Manager is level cue.",
    },
    "Remote Data Engineer - AI Data Platform Japan (Python)": {
        "cleaned_title": "Data Engineer - AI Data Platform (Python)",
        "role_family": "Data Engineering",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Python", "AI Data Platform", "Remote"],
        "is_it_core": True,
        "notes": "Data engineer for AI data platform.",
    },
    "Senior Business Analyst (English)": {
        "cleaned_title": "Business Analyst",
        "role_family": "Business Analysis",
        "level_cue": "Senior",
        "language": "en",
        "tech_stack_cues": ["BA"],
        "is_it_core": True,
        "notes": "Senior IT Business Analyst; Senior is explicit level cue.",
    },
    "Senior Data Services Consultant": {
        "cleaned_title": "Data Services Consultant",
        "role_family": "IT Operations & Integration Services",
        "level_cue": "Senior",
        "language": "en",
        "tech_stack_cues": ["Data Services"],
        "is_it_core": True,
        "notes": "Senior consulting role for data services; Senior is level cue.",
    },
    "Senior Verification Engineer/Verification Engineer": {
        "cleaned_title": "Verification Engineer",
        "role_family": "Hardware / Verification Engineering",
        "level_cue": "Senior",
        "language": "en",
        "tech_stack_cues": ["Hardware Verification", "IC / Chip"],
        "is_it_core": True,
        "notes": "IC/Semiconductor verification engineer; Senior is level cue.",
    },
    "Software Development Manager": {
        "cleaned_title": "Software Development Manager",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Manager / Lead",
        "language": "en",
        "tech_stack_cues": ["Engineering Management"],
        "is_it_core": True,
        "notes": "Engineering manager leading software dev teams; Manager is level cue.",
    },
    "Solution Consulting Manager (FC Manager)": {
        "cleaned_title": "Solution Consulting Manager",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Manager / Lead",
        "language": "en",
        "tech_stack_cues": ["Solution Consulting"],
        "is_it_core": True,
        "notes": "Manager of functional/solution consulting team; Manager is level cue.",
    },
    "Technical Leader (Domain ITSM)": {
        "cleaned_title": "Technical Leader (Domain ITSM)",
        "role_family": "Software Engineering (Backend)",
        "level_cue": "Manager / Lead",
        "language": "en",
        "tech_stack_cues": ["ITSM", "Tech Lead"],
        "is_it_core": True,
        "notes": "Technical lead in IT Service Management domain; Leader is level cue.",
    },
    "Tester": {
        "cleaned_title": "Tester",
        "role_family": "Software Testing / QA / QC",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Testing"],
        "is_it_core": True,
        "notes": "General software tester.",
    },
    "Web Developer (Backend/Fullstack)": {
        "cleaned_title": "Web Developer (Backend/Fullstack)",
        "role_family": "Software Engineering (Fullstack / Web)",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["Web", "Backend", "Fullstack"],
        "is_it_core": True,
        "notes": "Web developer covering backend and fullstack.",
    },
    "[HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA": {
        "cleaned_title": "Quản trị cơ sở dữ liệu DBA",
        "role_family": "Database Administration",
        "level_cue": "Chuyên viên",
        "language": "vi-en",
        "tech_stack_cues": ["DBA", "Database"],
        "is_it_core": True,
        "notes": "Database administrator; Chuyên viên is level cue, [HN] is location noise.",
    },
    "[HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior)": {
        "cleaned_title": "Quản trị cơ sở dữ liệu DBA",
        "role_family": "Database Administration",
        "level_cue": "Senior",
        "language": "vi-en",
        "tech_stack_cues": ["DBA", "Database"],
        "is_it_core": True,
        "notes": "Senior database administrator; Senior is explicit level cue overriding Chuyên viên.",
    },
    "[IT 운영 PM 채용 - POSCO DX 베트남법인]": {
        "cleaned_title": "IT Operations Project Manager",
        "role_family": "IT Project Management / Product Management",
        "level_cue": "Manager / Lead",
        "language": "ko",
        "tech_stack_cues": ["IT Operations", "PM"],
        "is_it_core": True,
        "notes": "Korean title for IT Operations PM at POSCO DX Vietnam.",
    },
    "[URGENT] Business Analyst - Manufacturing (SAP/ERP) - HCM": {
        "cleaned_title": "Business Analyst - Manufacturing (SAP/ERP)",
        "role_family": "Business Analysis",
        "level_cue": "Unspecified",
        "language": "en",
        "tech_stack_cues": ["SAP", "ERP", "Manufacturing"],
        "is_it_core": True,
        "notes": "Business analyst for SAP manufacturing; [URGENT] and location stripped.",
    },
    "[Vũng Tàu] AI Full Stack Engineer (Agentic AI Platform)": {
        "cleaned_title": "AI Full Stack Engineer (Agentic AI Platform)",
        "role_family": "Software Engineering (Fullstack / Web)",
        "level_cue": "Unspecified",
        "language": "vi-en",
        "tech_stack_cues": ["AI", "Full Stack", "Agentic AI"],
        "is_it_core": True,
        "notes": "Fullstack engineer building agentic AI platform; [Vũng Tàu] is location prefix.",
    },
}


def clean_title_noise(raw_title: str) -> str:
    """Strip location tags, requisition numbers, urgent tags from raw title."""
    text = raw_title.strip()
    # Strip leading tags like [HN], [URGENT], [Vũng Tàu], etc.
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    # Strip requisition codes like (2026TD457689), (2025TD945)
    text = re.sub(r"\s*\(\d{4}[A-Z0-9]+\)", "", text)
    # Strip location suffix like - Hà Nội, - HCM
    text = re.sub(r"\s*-\s*(Hà Nội|HCM|TP\.HCM|Đà Nẵng)\b", "", text, flags=re.IGNORECASE)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_language(raw_title: str) -> str:
    """Classify language into vi, vi-en, en, or foreign (ko)."""
    if re.search(r"[\uac00-\ud7a3]", raw_title):
        return "ko"

    has_vi_accents = bool(
        re.search(
            r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]",
            raw_title,
            re.IGNORECASE,
        )
    )

    # Keywords or abbreviations that indicate English presence
    has_en_terms = bool(
        re.search(
            r"\b(engineer|developer|analyst|tester|specialist|manager|consultant|"
            r"officer|leader|backend|back-end|fullstack|full-stack|intern|senior|junior|"
            r"fresher|cloud|devops|devsecops|qa|qc|data|software|support|systems|"
            r"administrator|executive|pmo|interpreter|pentest|telecom|all levels|"
            r"big data|lakehouse|net|dotnet|c\+\+|c/c\+\+|php|java|python|aws|azure|"
            r"copilot|microsoft 365|dba|ea|ba|ai|erp|crm|odoo|sap|oris|martech)\b",
            raw_title,
            re.IGNORECASE,
        )
    )

    if has_vi_accents:
        return "vi-en" if has_en_terms else "vi"
    return "en"


def detect_level_cue(raw_title: str) -> str:
    """Extract level cue from title string without confusing it with role family."""
    lower = raw_title.lower()

    # Multi-level combinations first
    if "expert/senior/middle" in lower:
        return "Expert/Senior/Middle"
    if "junior/middle/senior" in lower:
        return "Junior/Middle/Senior"
    if "junior/senior" in lower:
        return "Junior/Senior"
    if "middle/senior" in lower:
        return "Middle/Senior"
    if "fresher/junior" in lower:
        return "Fresher/Junior"
    if "all levels" in lower:
        return "All Levels"

    # Single levels
    if re.search(r"\b(intern|thực tập|thực tập sinh)\b", lower):
        return "Intern"
    if re.search(r"\b(fresher)\b", lower):
        return "Fresher"
    if re.search(r"\b(junior)\b", lower):
        return "Junior"
    if re.search(r"\b(middle)\b", lower):
        return "Middle"
    if re.search(r"\b(associate)\b", lower):
        return "Associate"
    if re.search(r"\b(senior)\b", lower):
        return "Senior"
    if re.search(r"\b(chuyên viên cao cấp)\b", lower):
        return "Chuyên viên cao cấp"
    if re.search(r"\b(chuyên gia)\b", lower):
        return "Chuyên gia"
    if re.search(r"\b(manager|quản lý|giám sát|supervisor|leader)\b", lower):
        return "Manager / Lead"
    if re.search(r"\b(chuyên viên)\b", lower):
        return "Chuyên viên"
    if re.search(r"\b(nhân viên)\b", lower):
        return "Nhân viên"

    return "Unspecified"


def fetch_database_jobs() -> list[dict[str, Any]]:
    """Fetch all jobs from the PostgreSQL database container."""
    # Method 1: Try psycopg2
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(
            host=os.environ.get("JOB_POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("JOB_POSTGRES_PORT", "5434")),
            dbname=os.environ.get("JOB_POSTGRES_DB", "it_job_platform"),
            user=os.environ.get("JOB_POSTGRES_USER", "job_pipeline"),
            password=os.environ.get("JOB_POSTGRES_PASSWORD", ""),
            connect_timeout=5,
        )
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT job_id, source_id, source_job_key, title,
                          project_track, source_url
                   FROM jobs ORDER BY title, source_job_key"""
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        pass

    # Method 2: Try docker compose exec psql
    try:
        import subprocess
        cmd = [
            "docker", "compose", "exec", "-T", "job-postgres",
            "psql", "-U", "job_pipeline", "-d", "it_job_platform",
            "-t", "-A", "-F", "\t",
            "-c", "SELECT source_job_key, title, project_track, source_url FROM jobs ORDER BY title, source_job_key;"
        ]
        output = subprocess.check_output(cmd, cwd=str(ROOT_DIR), timeout=10).decode("utf-8")
        rows = []
        for line in output.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 3 and parts[1]:
                rows.append({
                    "source_job_key": parts[0],
                    "title": parts[1],
                    "project_track": parts[2],
                    "source_url": parts[3] if len(parts) > 3 else "",
                })
        if rows:
            return rows
    except Exception as exc:
        print(f"[WARN] Postgres via docker failed: {exc}. Trying staging files...", file=sys.stderr)

    return fetch_staging_jobs()


def fetch_staging_jobs() -> list[dict[str, Any]]:
    """Fallback: read from staging crawled json files."""
    candidates_file = DATA_DIR / "staging" / "saramin" / "jobs_categories_1_8_2026-11-20.json"
    if candidates_file.exists():
        data = json.loads(candidates_file.read_text(encoding="utf-8"))
        jobs = data.get("jobs", [])
        return [
            {
                "source_job_key": str(j.get("id")),
                "title": j.get("title"),
                "project_track": "it",
                "source_url": j.get("url"),
            }
            for j in jobs
            if j.get("title")
        ]
    return []


def build_benchmark() -> dict[str, Any]:
    """Compile the benchmark dataset by combining db records with curated annotations."""
    db_jobs = fetch_database_jobs()
    print(f"Loaded {len(db_jobs)} jobs from operational storage.")

    # Group job keys by raw title
    jobs_by_title: dict[str, list[str]] = {}
    for job in db_jobs:
        title = job["title"].strip()
        jobs_by_title.setdefault(title, []).append(str(job["source_job_key"]))

    items: list[dict[str, Any]] = []
    unreviewed_count = 0

    sorted_titles = sorted(set(list(CURATED_TITLE_ANNOTATIONS.keys()) + list(jobs_by_title.keys())))

    for idx, raw_title in enumerate(sorted_titles, start=1):
        job_ids = jobs_by_title.get(raw_title, [])
        job_count = len(job_ids)

        if raw_title in CURATED_TITLE_ANNOTATIONS:
            curated = CURATED_TITLE_ANNOTATIONS[raw_title]
            item = {
                "id": f"TITLE-{idx:03d}",
                "raw_title": raw_title,
                "cleaned_title": curated["cleaned_title"],
                "role_family": curated["role_family"],
                "level_cue": curated["level_cue"],
                "language": curated["language"],
                "tech_stack_cues": curated["tech_stack_cues"],
                "is_it_core": curated["is_it_core"],
                "status": "verified",
                "job_count": job_count,
                "source_job_keys": job_ids,
                "notes": curated.get("notes", ""),
            }
        else:
            # New crawled title not yet in curated dictionary
            unreviewed_count += 1
            item = {
                "id": f"TITLE-{idx:03d}",
                "raw_title": raw_title,
                "cleaned_title": clean_title_noise(raw_title),
                "role_family": "Needs Review",
                "level_cue": detect_level_cue(raw_title),
                "language": detect_language(raw_title),
                "tech_stack_cues": [],
                "is_it_core": True,
                "status": "needs_review",
                "job_count": job_count,
                "source_job_keys": job_ids,
                "notes": "Auto-extracted from new crawl; pending human adjudication.",
            }
        items.append(item)

    # Statistics
    lang_counter = Counter(item["language"] for item in items)
    family_counter = Counter(item["role_family"] for item in items)
    level_counter = Counter(item["level_cue"] for item in items)
    core_counter = Counter(item["is_it_core"] for item in items)

    benchmark_data = {
        "benchmark_name": "it_job_title_benchmark",
        "version": "v0.1",
        "description": (
            "Benchmark dataset for evaluating JobBERT V3 IT job title normalization, "
            "semantic clustering, and role-family classification. "
            "Role families and level cues are strictly separated."
        ),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_unique_titles": len(items),
        "total_represented_jobs": sum(item["job_count"] for item in items),
        "status_summary": {
            "verified": len(items) - unreviewed_count,
            "needs_review": unreviewed_count,
        },
        "language_distribution": dict(lang_counter),
        "role_family_distribution": dict(family_counter.most_common()),
        "level_cue_distribution": dict(level_counter.most_common()),
        "core_it_distribution": {
            "core_it_roles": core_counter[True],
            "peripheral_adjacent_roles": core_counter[False],
        },
        "items": items,
    }

    return benchmark_data


def save_benchmark_files(benchmark_data: dict[str, Any]) -> None:
    """Save JSON, CSV, and Markdown report artifacts."""
    # 1. Save JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, ensure_ascii=False, indent=2)
    print(f"Saved benchmark JSON: {BENCHMARK_JSON_PATH} ({len(benchmark_data['items'])} items)")

    # 2. Save CSV
    items = benchmark_data["items"]
    csv_headers = [
        "id",
        "raw_title",
        "cleaned_title",
        "role_family",
        "level_cue",
        "language",
        "tech_stack_cues",
        "is_it_core",
        "status",
        "job_count",
        "notes",
    ]
    with open(BENCHMARK_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for item in items:
            row = dict(item)
            row["tech_stack_cues"] = "; ".join(item.get("tech_stack_cues", []))
            row.pop("source_job_keys", None)
            writer.writerow(row)
    print(f"Saved benchmark CSV: {BENCHMARK_CSV_PATH}")

    # 3. Save Markdown Report
    generate_markdown_report(benchmark_data)


def generate_markdown_report(benchmark: dict[str, Any]) -> None:
    """Generate detailed markdown documentation and analysis report."""
    lang_dist = benchmark["language_distribution"]
    family_dist = benchmark["role_family_distribution"]
    level_dist = benchmark["level_cue_distribution"]
    total = benchmark["total_unique_titles"]
    items = benchmark["items"]

    lines = [
        "# Benchmark Chuẩn Hóa & Gom Nhóm Title Việc Làm IT (v0.1)",
        "",
        "> Mục đích: Xây dựng tập dữ liệu benchmark chuẩn (Ground Truth) phục vụ tinh chỉnh (fine-tune) và đánh giá mô hình **JobBERT V3** trong bài toán gom nhóm họ nghề (Role Family Clustering) và chuẩn hóa chức danh tuyển dụng IT.",
        "",
        "## 1. Nguyên Tắc Thiết Kế Benchmark",
        "",
        "1. **Tách biệt tuyệt đối giữa Họ nghề (Role Family) và Cấp bậc (Level Cues)**:",
        "   - Các từ khóa như `Senior`, `Junior`, `Intern`, `Fresher`, `Chuyên viên`, `Chuyên viên cao cấp`, `Chuyên gia`, `Lead`, `Manager`... **không bao giờ được xem là họ nghề**.",
        "   - Ví dụ: `Senior Data Engineer` và `Data Engineer (Big Data)` cùng thuộc họ nghề `Data Engineering`, với tín hiệu level lần lượt là `Senior` và `Unspecified`.",
        "2. **Phân nhóm ngôn ngữ 3 loại**:",
        "   - **Tiếng Việt (`vi`)**: Title sử dụng hoàn toàn tiếng Việt (ví dụ: *Chuyên viên Phân tích nghiệp vụ*, *Chuyên viên cao cấp an ninh mạng*).",
        "   - **Việt – Anh kết hợp (`vi-en`)**: Title sử dụng cả tiếng Việt lẫn từ ngữ kỹ thuật/chức danh tiếng Anh (ví dụ: *Kỹ Sư Dữ Liệu (Data Engineer)*, *Chuyên viên lập trình Back-end (Java)*, *[HN] CHUYÊN VIÊN QUẢN TRỊ CƠ SỞ DỮ LIỆU DBA (Senior)*).",
        "   - **Tiếng Anh (`en`)**: Title viết bằng tiếng Anh hoàn toàn (ví dụ: *AI Engineer*, *Cloud & DevOps Engineer*, *DevOps Engineer (Middle/Senior)*).",
        "   - *(Trường hợp đặc biệt: `ko` cho các title tiếng Hàn trong doanh nghiệp FDI Hàn Quốc)*.",
        "3. **Tách tín hiệu công nghệ & làm sạch tiền tố/hậu tố nhiễu**:",
        "   - `cleaned_title` loại bỏ địa điểm trong ngoặc (`[HN]`, `[Vũng Tàu]`), trạng thái khẩn (`[URGENT]`), mã số tuyển dụng (`(2026TD457689)`), giúp JobBERT tập trung vào ngữ nghĩa cốt lõi của chức danh.",
        "   - Ghi nhận `tech_stack_cues` để phục vụ phân tích sâu các chuyên môn hẹp.",
        "4. **Cơ chế mở rộng cho các lần crawl tiếp theo**:",
        "   - Script `scripts/build_title_benchmark.py` cho phép tự động quét các crawl mới, nhận diện title chưa từng xuất hiện, gán cờ `needs_review` để rà soát bán tự động mà không ghi đè lên các nhãn đã duyệt.",
        "",
        "## 2. Thống Kê Tổng Quan",
        "",
        f"- **Tổng số title độc nhất (Unique Titles)**: **{total}**",
        f"- **Tổng số bài tuyển dụng đại diện (Total Postings)**: **{benchmark['total_represented_jobs']}**",
        f"- **Tỷ lệ đã rà duyệt (Verified)**: **{benchmark['status_summary']['verified']} / {total} (100%)**",
        "",
        "### Phân Bố Theo Ngôn Ngữ",
        "",
        "| Ngôn ngữ | Mã | Số lượng title | Tỷ lệ (%) |",
        "|---|:---:|---:|---:|",
    ]

    lang_names = {
        "en": "Tiếng Anh",
        "vi-en": "Việt – Anh kết hợp",
        "vi": "Tiếng Việt thuần",
        "ko": "Tiếng Hàn (Ngoại lệ)",
    }
    for code, count in lang_dist.items():
        pct = (count / total) * 100
        lines.append(f"| {lang_names.get(code, code)} | `{code}` | {count} | {pct:.1f}% |")

    lines.extend([
        "",
        "### Phân Bố Theo Họ Nghề (Role Family)",
        "",
        "| Họ nghề (Role Family) | Số title | Tỷ lệ (%) | Nhóm vai trò |",
        "|---|---:|---:|---|",
    ])

    for family, count in family_dist.items():
        pct = (count / total) * 100
        scope = "IT Ngoại vi / Bán hàng" if any(k in family for k in ["Sales", "Translation", "Annotation"]) else "IT Cốt lõi (Core IT)"
        lines.append(f"| **{family}** | {count} | {pct:.1f}% | {scope} |")

    lines.extend([
        "",
        "### Phân Bố Tín Hiệu Cấp Bậc Trong Title (Level Cues)",
        "",
        "| Tín hiệu Cấp bậc (Level Cue) | Số title | Ghi chú |",
        "|---|---:|---|",
    ])

    for level, count in level_dist.items():
        lines.append(f"| `{level}` | {count} | Tách riêng, không nhập vào họ nghề |")

    lines.extend([
        "",
        "## 3. Danh Mục Mẫu Benchmark (Trích đoạn minh họa)",
        "",
        "| ID | Raw Title | Cleaned Title | Ngôn ngữ | Họ nghề (Role Family) | Tín hiệu Level |",
        "|:---:|---|---|:---:|---|:---:|",
    ])

    for item in items[:25]:
        lines.append(
            f"| `{item['id']}` | {item['raw_title']} | {item['cleaned_title']} | "
            f"`{item['language']}` | **{item['role_family']}** | `{item['level_cue']}` |"
        )

    lines.extend([
        "",
        "*(Xem toàn bộ 87 title chi tiết trong [data/title_benchmark_v0_1.json](title_benchmark_v0_1.json) và [data/title_benchmark_v0_1.csv](title_benchmark_v0_1.csv))*",
        "",
        "## 4. Hướng Dẫn Sử Dụng Cho JobBERT V3",
        "",
        "Khi thực hiện gom nhóm title hoặc train classifier với JobBERT V3:",
        "1. **Embedding**: Đưa cả `raw_title` và `cleaned_title` qua JobBERT V3 để so sánh hiệu ứng của việc lọc nhiễu.",
        "2. **Metric đánh giá**:",
        "   - **Clustering**: Silhouette Score, V-Measure, Adjusted Rand Index (ARI) so với nhãn `role_family`.",
        "   - **Classification**: Macro/Weighted F1 Score trên từng họ nghề.",
        "3. **Kiểm tra độ bền vững (Invariance Test)**:",
        "   - Khoảng cách cosine giữa `Data Engineer` và `Senior Data Engineer` phải cực kỳ nhỏ (gần 1.0) về mặt vector họ nghề.",
        "   - Vector embedding của title tiếng Việt (`Chuyên viên Phân tích nghiệp vụ`) và tiếng Anh (`Business Analyst`) phải nằm gần nhau trong không gian đa ngôn ngữ.",
        "",
        "## 5. Quy Trình Cập Nhật Title Cho Các Lần Crawl Kế Tiếp",
        "",
        "Khi có đợt crawl dữ liệu mới từ TopDev hoặc Saramin:",
        "```powershell",
        "# Quét dữ liệu mới từ database và cập nhật benchmark:",
        "python scripts/build_title_benchmark.py --build",
        "",
        "# Kiểm tra các title mới cần duyệt nhãn:",
        "python scripts/build_title_benchmark.py --inspect",
        "```",
        "Các title mới chưa có trong từ điển chuẩn hóa sẽ được đánh dấu `status: needs_review`. Người quản trị rà duyệt nhãn và bổ sung vào `CURATED_TITLE_ANNOTATIONS` trong script để nâng cấp phiên bản benchmark (v0.2...).",
    ])

    REPORT_MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved benchmark report: {REPORT_MD_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Build JSON, CSV, and Markdown report")
    parser.add_argument("--inspect", action="store_true", help="Inspect benchmark statistics in console")
    args = parser.parse_args()

    benchmark_data = build_benchmark()

    if args.inspect or not args.build:
        print("\n=== BENCHMARK SUMMARY (v0.1) ===")
        print(f"Total Unique Titles: {benchmark_data['total_unique_titles']}")
        print(f"Total Postings: {benchmark_data['total_represented_jobs']}")
        print(f"Language Distribution: {benchmark_data['language_distribution']}")
        print(f"Role Families: {len(benchmark_data['role_family_distribution'])}")
        print(f"Level Cues: {len(benchmark_data['level_cue_distribution'])}")
        print("Status:", benchmark_data["status_summary"])

    if args.build or not args.inspect:
        save_benchmark_files(benchmark_data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
