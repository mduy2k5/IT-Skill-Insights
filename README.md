# IT Job ETL Pipeline & Analytics Dashboard

An end-to-end automated pipeline for collecting, transforming, and analyzing IT job market data from recruitment websites. 

This project bridges Data Engineering and Data Analytics by using **Scrapy**, **PostgreSQL**, **Apache Airflow**, **Docker**, and **Flask** to build a scalable data platform, and **Power BI** to deliver interactive, actionable market insights.

# 🚀 Project Goals

The system is designed to:

- Crawl IT job data from recruitment websites.
- Visit job detail pages to extract: Responsibilities, Skills, Benefits.
- Normalize raw job data and extract technical skills using RegEx.
- Standardize job titles into unified categories.
- Build APIs for job searching and analytics.
- Model data into a structured Star Schema (Fact and Dimension tables) optimized for BI reporting.
- Develop an interactive Power BI Dashboard providing actionable insights on market trends, skill demands, and job distributions.

# 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Web Crawling | Scrapy |
| Data Processing | Python |
| Database | PostgreSQL |
| Workflow Orchestration | Apache Airflow |
| Containerization | Docker |
| Backend API | Flask |
| Data Modeling | Star Schema (Dim-Fact Model) |
| Data Visualization | Power BI, DAX |

# 📂 Project Structure

```text
IT_JOB_PIPELINE/
│
├── dags/                                  # Airflow DAG definitions
│   ├── __pycache__/
│   └── job_pipeline.py                    # Main ETL pipeline DAG
│
├── data/                                  # Mapping datasets
│   ├── job_skills.csv                     # Skill dictionary
│   └── job_titles.csv                     # Job title normalization dictionary
│
├── logs/                                  # Airflow logs
│
├── plugins/                               # Airflow plugins
│
├── scraper/
│   │
│   ├── job_crawler/
│   │   ├── __pycache__/
│   │   │
│   │   ├── spiders/                       # Scrapy spiders
│   │   │   ├── __pycache__/
│   │   │   ├── __init__.py
│   │   │   ├── it_jobs.py                 # Crawl job list
│   │   │   └── it_jobs_detail.py          # Crawl job detail
│   │   │
│   │   ├── transform/                     # Data transformation modules
│   │   │   ├── __pycache__/
│   │   │   ├── __init__.py
│   │   │   ├── base_transformer.py
│   │   │   ├── database.py                # PostgreSQL connection
│   │   │   ├── weba_transformer.py
│   │   │   └── webb_transformer.py
│   │   │
│   │   ├── __init__.py
│   │   ├── items.py                       # Scrapy item definitions
│   │   ├── job_skill_requirement_transform.py
│   │   ├── job_title_transform.py
│   │   ├── middlewares.py
│   │   ├── pipelines.py                   # Scrapy pipelines
│   │   ├── run_transform.py               # Run all transforms
│   │   └── settings.py                    # Scrapy settings
│   │
│   ├── venv/
│   ├── Dockerfile
│   └── scrapy.cfg
│
├── web/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   │
│   │   └── js/
│   │       └── main.js
│   │
│   ├── templates/
│   │   └── index.html
│   │
│   ├── app.py                             # Flask application
│   ├── Dockerfile
│   └── requirements.txt
│
├── .dockerignore
├── .gitignore
└── docker-compose.yml
```

# 📌 Main Features
## 1. Job Crawling
The system uses Scrapy spiders to crawl:
- Job title & Company
- Salary & Location
- Experience & Job level
- Job type & Tags
- Posted date & Company logo
- Job detail links

## 2. Job Detail Extraction
A second spider crawls each job detail page to collect:
- Responsibilities
- Required skills
- Benefits

# 🧹 Data Transformation
The project applies ETL transformations to normalize and clean raw data.

Data Standardization
The system normalizes Company names, Locations, Job levels, Job types, and Dates using mapping tables and transformation modules.

# 🏗️ Data Warehouse Design
The project follows a Dim-Fact model (Star Schema) to resolve many-to-many relationships and optimize analytical query performance.

Main Fact Table
```SQL
CREATE TABLE jobs_clean (
    id SERIAL PRIMARY KEY,
    job_title TEXT,
    company_id INTEGER,
    salary TEXT,
    location_id INTEGER,
    job_type_id INTEGER,
    experience TEXT,
    tags_id TEXT[],
    posted_at_id INTEGER,
    link TEXT UNIQUE,
    logo_link TEXT,
    responsibilities TEXT,
    skills TEXT,
    benefits TEXT,
    source TEXT DEFAULT 'job_crawler',
    job_title_mapping_id INTEGER
);
```
# 🧠 Skill Extraction
The system extracts skills from job descriptions using Regex, Keyword matching, and Skill dictionaries (e.g., Python, SQL, PostgreSQL, Docker, Airflow, ETL).

Skill Dimension
```SQL
CREATE TABLE dim_skill (
    skill_id SERIAL PRIMARY KEY,
    skill_keyword VARCHAR(100) UNIQUE NOT NULL,
    skill_group VARCHAR(100) NOT NULL
);
```
Skill Mapping Table
```SQL
CREATE TABLE fact_job_skill_mapping (
    job_id INT REFERENCES jobs_clean(id) ON DELETE CASCADE,
    skill_id INT REFERENCES dim_skill(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);
```
# 💼 Job Title Normalization
Different companies may use different titles for the same role (e.g., Data Engineer, ETL Developer, Data Pipeline Engineer). The project standardizes them into common job groups using a mapping dataset.

Job Title Dimension
```SQL
CREATE TABLE dim_job_title (
    job_title_id SERIAL PRIMARY KEY,
    job_title VARCHAR(255) UNIQUE NOT NULL,
    job_group VARCHAR(100) NOT NULL
);
```
# 📊 Analytics & Interactive Dashboard (Power BI)
The analytical front-end of this pipeline is a dynamic Power BI dashboard designed to provide stakeholders with deep insights into the IT job market. It connects directly to the PostgreSQL Data Warehouse.
![DashboardA](https://github.com/mduy2k5/IT-Job-ETL-Pipeline/blob/main/PowerBI/DashBoardA.png)
![DashboardB](https://github.com/mduy2k5/IT-Job-ETL-Pipeline/blob/main/PowerBI/DashBoardB.png)
## Core Analytical Features
- Dynamic Dimensionality (Field Parameters): Implemented DAX Field Parameters allowing users to instantly pivot the analytical axis. Users can seamlessly switch between viewing job distributions by Tech Category (e.g., Engineering, Data) or Seniority Level (e.g., Junior, Senior) within the exact same visual footprint.
- Advanced DAX Measures: Utilized context transition (CALCULATE, MAXX, MINX) and dynamic filtering logic to accurately aggregate job counts and skill demands across complex bridging tables (resolving many-to-many relationships between jobs and skills).
- Market Trend Analysis: Statistical tracking of job distribution across provinces/categories, most in-demand skills mapped to specific job groups, and required experience level distributions.

## UI/UX Engineering
- Seamless Visual Toggling: Engineered a state-driven UI using Power BI Bookmarks and the Selection Pane. Users can toggle between comparative views (Bar Chart) and proportional views (Pie/Donut Chart) without visual clutter, while keeping all slicer selections fully intact.
- High-Level KPIs: Clear, top-level KPI cards provide immediate context on total Jobs Count, Date ranges, and Location metrics.

# 🔄 Airflow Workflow
The ETL pipeline is orchestrated using Apache Airflow.
DAG Workflow:
```Plaintext
crawl_jobs
    ↓
crawl_job_detail
    ↓
transform_jobs
    ↓
transform_skills
    ↓
transform_job_titles
```
# 🐳 Docker Deployment
The entire system is containerized using Docker. Services include PostgreSQL, Airflow, Scrapy, and the Flask API.
Run the Project
```Bash
docker compose up --build
```
# 🌐 Flask API
The project exposes APIs for frontend dashboards and data access.
Example endpoints:
```HTTP
GET /jobs
GET /skills
GET /analysis/top-skills
GET /analysis/job-groups
```
# 📈 Future Improvements
Potential future enhancements:
- Salary band estimation and analysis.
- NLP-based skill extraction (replacing RegEx).
- Real-time streaming data ingestion.
- Implement Row-Level Security (RLS) in Power BI for localized recruiter views.
- Migrate dashboard to Power BI Service with scheduled automated refreshes via On-premises Data Gateway.

# ⚠️ Notes
- Data is collected from publicly accessible recruitment websites.
- Website names and sensitive information are hidden.
- Default database credentials are for development/demo purposes only.
- Environment variables can be customized using .env.

# 👨‍💻 Author
Developed by Duy Mai

Tech Stack: Scrapy • PostgreSQL • Airflow • Docker • Flask • Power BI
