# Offerion

Standalone resume-to-offer engine.

## Module 1 — Engine Foundation

Clean Flask app structure with homepage route.

## Module 2 — Resume Upload

Upload a resume file through the browser. The file is saved locally to the `uploads/` folder.

## Module 3 — Resume Text Extraction

After uploading, the app extracts readable text from the resume and shows a preview.

**Supported extraction:**

- `.pdf` — extracted via pdfplumber
- `.docx` — extracted via python-docx

**Current limitation:** `.doc` files are accepted for upload but text extraction is not yet supported. A clear message is shown.

**Preview:** The first ~2000 characters of extracted text are displayed. If the resume is longer, the preview is truncated.

## Module 4 — Structured Resume Analysis

After extraction, the app analyzes the resume text and displays a structured profile summary.

**Detected fields:**

- **Name** — inferred from the first few lines of the resume
- **Email** — detected via regex
- **Phone** — detected via regex
- **Skills** — matched against a built-in keyword list (case-insensitive)
- **Education Indicators** — lines containing degree/school keywords
- **Experience Indicators** — lines containing job-related keywords or year patterns

This is rule-based local parsing only. No AI or LLM calls are used. Fields that cannot be detected show "Not detected".

## Module 5 — Target Role Match Scoring

Enter a target job title and optional keywords alongside your resume upload. The app compares your extracted skills, text, and profile indicators against the target and produces:

- **Match Score** (0–100)
- **Match Level** — Low (0–39), Moderate (40–69), Strong (70–100)
- **Matched Items** — target terms found in your resume
- **Missing Items** — target terms not found
- **Explanation** — a short summary of the match result

Scoring is rule-based and local. No AI, LLM, or external API calls are used.

## Module 6 — Suggested Roles

After extracting and analyzing your resume, Offerion automatically suggests 3–5 likely target roles from a built-in catalog of 12 roles. Each suggestion includes:

- **Role name**
- **Score** (0–100) and **Level** (Low / Moderate / Strong)
- **Matched indicators** — keywords found in your resume
- **Reason** — short explanation of why this role was suggested

The catalog includes roles like Software Engineer, Data Analyst, Project Manager, Marketing Specialist, and more. Suggestions are rule-based and local — no AI or external APIs.

## Module 7 — Resume Improvement Guidance

After analysis, Offerion provides a structured improvement report with four sections:

- **Strengths** — what the resume already does well (contact info, skills count, alignment with target role)
- **Gaps** — what is missing or weak (missing contact details, low skill count, missing target keywords)
- **Recommendations** — actionable steps to improve the resume for the target role
- **Completeness** — a checklist showing which key resume fields were detected (name, email, phone, skills, education, experience, text length)

If a target role match was scored, feedback incorporates missing keywords and match strength. All logic is rule-based and local — no AI or external APIs.

## Module 8 — Downloadable Analysis Report

After completing a resume analysis, a **Download Report** button appears. Clicking it downloads a plain-text `.txt` file containing the full Offerion analysis:

- **File Information** — uploaded filename, type, and extraction status
- **Resume Profile Summary** — name, email, phone, skills, education, experience
- **Match Analysis** — target role, score, matched/missing keywords, explanation (if a target role was entered)
- **Suggested Roles** — top role suggestions with scores and reasons
- **Resume Improvement Guidance** — strengths, gaps, recommendations, and completeness checklist

The report is generated on the server from session data stored during the most recent analysis. No database is used — the data lives only in the current browser session.

## Module 11 — Storage Abstraction Layer

Uploaded files are now handled through a **storage abstraction layer** (`app/utils/storage.py`) instead of direct filesystem calls in routes.

**Key changes:**

- **Unique filenames** — each upload is saved with a UUID suffix to prevent overwrites
- **Temp directory** — files are stored in `/tmp/uploads` (Render-friendly) instead of the project root
- **Auto-cleanup** — uploaded files are deleted immediately after processing
- **Error safety** — the app will not crash if an uploaded file is missing or cannot be saved
- **Cloud-ready** — the storage module can be swapped to use S3, GCS, or any cloud provider by updating `save_file()`, `get_file_path()`, and `delete_file()` without changing any other code

**Current limitation:** Files are temporary and not persisted across deploys or restarts. A future module will integrate real persistent cloud storage (e.g., AWS S3).

## Module 12 — Job Description Comparison Engine

Paste a job description alongside your resume upload to get a tailored comparison analysis.

**How it works:**

1. Upload a resume and optionally enter a target role/keywords
2. Paste a full job description into the new text area
3. The app extracts keywords from the job description using a built-in keyword library
4. It compares those keywords against your resume text and detected skills

**Comparison output:**

- **Overlap Score** (0–100) and **Fit Level** (Low / Moderate / Strong)
- **JD Keywords** — all recognized keywords found in the job description
- **Matched** — JD keywords found in your resume
- **Missing** — JD keywords not found in your resume
- **Explanation** — a readable summary of the comparison

**Integration:**

- Missing JD keywords are incorporated into Resume Improvement Guidance recommendations
- The downloadable report includes a Job Description Comparison section when a JD is provided
- If no job description is pasted, the section is hidden — existing behavior is unchanged

All comparison logic is rule-based and local. No live job scraping, AI, or external APIs are used.

## Module 13 — ATS Rewrite Guidance

After analysis, Offerion generates structured rewrite guidance to help you tailor your resume for ATS (Applicant Tracking System) screening.

**Guidance sections:**

- **Summary Focus** — how to write or improve your professional summary for the target role
- **Keyword Additions** — specific missing keywords to add to your resume (from target role and/or job description)
- **Bullet Improvements** — tips for rewriting experience bullets with stronger action verbs and measurable outcomes
- **Section Improvements** — structural suggestions (contact info, skills layout, education, formatting)
- **ATS Notes** — overall ATS readiness assessment based on your scores and keyword overlap

**Behavior:**

- If a job description is pasted, guidance incorporates JD-specific keyword gaps
- If a target role is entered, guidance references match score and missing terms
- If neither is provided, general best-practice guidance is still generated
- The downloadable report includes the ATS Rewrite Guidance section when available

All guidance is rule-based and local. No AI-powered rewriting is performed yet — a future module may add that capability.

## Run Locally

```
cd /d K:\Offerion
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000 in your browser.

## Deploy to Render

### Service Settings

| Setting       | Value                             |
| ------------- | --------------------------------- |
| Service Type  | Web Service                       |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app.main:app`           |

### Environment Variables

| Variable         | Value                             |
| ---------------- | --------------------------------- |
| `SECRET_KEY`     | A strong random string (required) |
| `PYTHON_VERSION` | `3.12.0` (optional)               |

Generate a secret key:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

### Important Limitation

Render uses **ephemeral storage**. Uploaded resume files are stored in memory on the server and will be lost when the service restarts or redeploys. This is expected — Offerion currently processes files per-request and does not persist uploads. Cloud storage may be added in a future module.
