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

| Setting        | Value                          |
|----------------|--------------------------------|
| Service Type   | Web Service                    |
| Build Command  | `pip install -r requirements.txt` |
| Start Command  | `gunicorn app.main:app`        |

### Environment Variables

| Variable     | Value                              |
|--------------|------------------------------------|
| `SECRET_KEY` | A strong random string (required)  |
| `PYTHON_VERSION` | `3.12.0` (optional)          |

Generate a secret key:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

### Important Limitation

Render uses **ephemeral storage**. Uploaded resume files are stored in memory on the server and will be lost when the service restarts or redeploys. This is expected — Offerion currently processes files per-request and does not persist uploads. Cloud storage may be added in a future module.
