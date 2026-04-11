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

## Module 14 — Resume Strength Scorecard

After analysis, Offerion displays a visual scorecard breaking down your resume quality across key categories.

**Scored categories (0–100):**

- **Contact Info** — based on whether name, email, and phone are detected
- **Skills Coverage** — based on the number of recognized skills
- **Experience Strength** — based on experience indicators and resume text richness
- **Education Completeness** — based on education indicators found
- **ATS Alignment** — based on target-role match score and/or JD comparison overlap
- **Overall Resume Strength** — weighted average of all categories

**Labels:** Each score maps to a label — Weak (0–39), Fair (40–59), Good (60–79), Strong (80–100).

**Highlights:** A short list of score-based takeaways identifying your strongest and weakest areas.

**Behavior:**

- Scorecard appears whenever a resume is analyzed (no target role or JD required)
- If target role and/or JD are provided, the ATS Alignment score incorporates them
- The downloadable report includes the scorecard section

All scoring is rule-based and local. No AI or external APIs are used.

## Module 15 — Tailored Resume Version Builder

After analysis, Offerion generates a structured tailored resume draft outline based on your uploaded resume, target role, optional job description, and detected strengths/gaps.

**Output fields:**

- **Target Title** — the role you are tailoring for (from target role input or JD)
- **Professional Summary Guidance** — step-by-step tips for writing a targeted summary
- **Priority Keywords** — keywords to feature, add, or keep, with status and action for each
- **Experience Focus Points** — how to reorder and rewrite experience bullets for the target role
- **Skills to Feature** — prioritized list of skills (high / medium / add) with color-coded tags
- **Section Focus** — which resume sections to strengthen, informed by scorecard scores
- **Tailoring Notes** — overall strategy notes based on alignment scores and analysis results

**Behavior:**

- Requires at least a target role or a pasted job description to generate output
- Incorporates data from match analysis, JD comparison, scorecard, and rewrite guidance when available
- Never fabricates experience — only reframes and prioritizes existing content
- The downloadable report includes the Tailored Resume Version Builder section when generated
- If neither a target role nor a job description is provided, the section is hidden

All logic is rule-based and local. No AI or external APIs are used.

## Module 18 — Downloadable Tailored Resume Brief

After analysis, if tailored resume data was generated, a **Download Tailored Brief** button appears alongside the existing Download Report button.

**What it includes:**

A focused plain-text export containing only the tailored resume guidance:

- **Target Title** — the role being tailored for
- **Professional Summary Guidance** — how to write a targeted summary
- **Priority Keywords** — keywords to feature or add, with status and action
- **Experience Focus Points** — how to reorder and rewrite experience bullets
- **Skills to Feature** — prioritized skill list with reasoning
- **Section Focus** — which resume sections to strengthen
- **Tailoring Notes** — overall strategy notes

**Behavior:**

- The button only appears when tailored data exists (requires a target role or JD)
- Downloads as `offerion_tailored_brief.txt`
- Does not affect or replace the full analysis report download
- Uses the same session data — no duplicate processing

All logic is rule-based and local. No AI or external APIs are used.

---

### Module 19 — Action Plan Panel

Generates a prioritized next-step checklist so users know exactly what to fix first.

**File:** `app/utils/action_plan.py`

**Function:** `generate_action_plan(scorecard, feedback, rewrite, tailored, jd_comparison)`

**Returns a dict with:**

- **top_priority** — single sentence identifying the most urgent fix
- **quick_wins** — 3–5 easy improvements to make right away
- **next_revision_steps** — 3–5 deeper revisions for the next draft
- **final_checklist** — 4–6 items with done/todo status

**UI:**

- Displayed as a card between the Scorecard and Resume Improvement Guidance sections
- Top Priority shown in an orange highlight banner
- Quick Wins and Next Revision Steps rendered as bullet lists
- Final Checklist uses ✓/✗ indicators

**Report:**

- ACTION PLAN section added to the downloadable report (between Tailored and End of Report)
- Includes Top Priority, Quick Wins, Next Revision Steps, and Final Checklist with [DONE]/[TODO] markers

All logic is rule-based and local. No AI or external APIs are used.

---

### Module 20 — Landing Value & Conversion Flow

UX/content upgrade to make the landing page clearer for first-time visitors.

**Changes (template only):**

- **Hero section** — replaced generic header with a strong headline ("Turn your resume into a role-ready action plan"), a one-sentence value proposition, and three benefit bullets
- **How It Works strip** — three horizontal step cards (Upload resume → Add context → Get your plan) placed below the hero
- **Upload card intro** — added a helper sentence explaining supported files and optional fields
- **Trust note** — subtle reassurance below the submit button that Offerion is guidance-focused and does not fabricate experience
- **CTA clarity** — surrounding context improved so the upload action feels obvious

No backend changes. Preserves the card-based dashboard layout from M16.

---

### Module 22 — Structured Resume Draft Export

Generates a downloadable plain-text resume draft template built from analysis outputs.

**File:** `app/utils/resume_draft_builder.py`

**Function:** `build_resume_draft(profile, tailored, rewrite, action_plan, match, jd_comparison)`

**Draft sections:**

- **Name & Contact Information** — pre-filled from detected profile data, with placeholders for missing fields
- **Target Title** — from tailored output or match target role
- **Professional Summary** — guidance-driven draft prompts from tailored/rewrite data
- **Core Skills** — prioritized skills to feature, plus missing keywords to add
- **Experience** — focus points and placeholder bullet templates (no fabricated content)
- **Education** — detected education or placeholder
- **ATS Alignment Notes** — keywords to weave in and ATS tips from rewrite guidance
- **Revision Checklist** — carried from action plan final checklist

**Route:** `/download-resume-draft` — returns `offerion_resume_draft.txt`

**UI:** Teal "Download Resume Draft" button alongside existing Report and Tailored Brief buttons.

**Behavior:**

- Uses bracketed placeholders like `[Add 2-3 quantified bullet points here]`
- Does not fabricate employers, dates, or achievements
- Available whenever analysis data exists (profile or tailored)
- Downloads as a plain-text guided editing template

All logic is rule-based and local. No AI or external APIs are used.

---

### Module 23 — Resume Preview Page

Adds a dedicated resume preview page that renders analysis data in a clean, resume-like layout.

**Template:** `app/templates/resume_preview.html`

**Route:** `/resume-preview` — renders the preview page from session data

**Preview sections:**

- **Name & Contact** — pre-filled from detected profile, placeholders for missing fields
- **Target Title** — from tailored output or match target role
- **Professional Summary** — guidance points from tailored data
- **Skills** — pill-tag layout from skills_to_feature or detected skills
- **Experience** — focus points plus placeholder bullet templates
- **Education** — detected education entries or placeholder
- **ATS Alignment Notes** — tips from rewrite guidance (if available)

**UI:**

- Dark "View Resume" button added to the results status bar alongside download buttons
- Preview page has "Download Resume Draft" and "Back to Dashboard" buttons at the bottom
- Clean, centered layout styled like a resume document
- Responsive design for mobile

**Behavior:**

- Redirects to dashboard if no analysis data exists in session
- Uses same session data as all other features — no duplicate processing
- Placeholders shown in italic grey for any missing sections

---

### Module 24 — AI Resume Enhancement Layer

Adds a deterministic enhancement layer that converts structured resume drafts into polished, professional language.

**File:** `app/utils/resume_enhancer.py`

**Function:** `enhance_resume(profile, tailored, rewrite, match)`

**Returns:**

- **name** — resolved from profile
- **contact** — formatted email | phone line
- **target_title** — from tailored or match data
- **enhanced_summary** — polished 2-4 sentence professional summary built from guidance points and skills
- **enhanced_skills** — deduplicated, priority-ordered skill list (max 12)
- **enhanced_experience_bullets** — action-oriented bullets derived from focus points and rewrite guidance (max 6)
- **enhanced_education** — education entries from profile
- **ats_alignment_notes** — ATS tips and keyword suggestions

**Routes:**

- `GET /enhance-resume` — runs enhancement, saves to session, redirects to preview
- Preview and download routes prefer enhanced data when available

**UI:**

- Purple "Enhance Resume" button on the preview page (hidden after enhancement)
- "ENHANCED" badge appears on the resume name after enhancement
- Summary displays as polished prose instead of bullet guidance
- Experience shows action-oriented bullets instead of placeholders

**Behavior:**

- Deterministic — no AI APIs, no external calls
- Does not fabricate employers, dates, or achievements
- Falls back to standard preview if enhancement not run
- Download outputs enhanced draft when available

All logic is rule-based and local. No AI or external APIs are used.

---

### Module 25 — Job-Targeted Resume Versioning

Save and manage multiple tailored resume versions per session so users can generate different resume variants for different target jobs.

**File:** `app/utils/resume_versioning.py`

**Functions:**

- `save_version(session_data)` — creates a snapshot of current report_data and enhanced_resume with unique id, label, and timestamp
- `load_version(version)` — returns deep copies of report_data and enhanced_resume from a saved version
- `find_version(versions, version_id)` — looks up a version by id
- `delete_version(versions, version_id)` — removes a version from the list

**Routes:**

- `GET /save-resume-version` — saves current state as a new version, redirects to preview
- `GET /resume-version/<id>` — loads a saved version into active session, redirects to preview
- `GET /resume-version/<id>/download` — downloads the saved version's resume draft directly
- `GET /delete-resume-version/<id>` — removes a saved version, redirects to dashboard

**UI:**

- "Save Version" teal button on the resume preview page
- Saved Resume Versions panel on dashboard (when versions exist) with Open, Download, Delete actions per entry
- Saved Resume Versions panel on preview page with same actions
- Labels derived from target title with timestamp; falls back to "Resume Version N"

**Behavior:**

- Session-based storage — no database required
- Deep copies prevent cross-version contamination
- Duplicate target titles allowed, distinguished by timestamp
- Opening a version restores both report_data and enhanced_resume
- Existing M22–M24 flow works unchanged when no versions are saved

---

### Module 26 — Cover Letter Draft Generator

Generates a structured cover letter draft from the active resume/job session.

**File:** `app/utils/cover_letter_builder.py`

**Function:** `build_cover_letter(profile, tailored, rewrite, match, enhanced_resume)`

**Returns:** dict with `recipient`, `company`, `target_title`, `opening`, `body_points`, `closing`, `full_text`

**Route:** `GET /generate-cover-letter` — builds draft, stores in session, redirects to preview

**UI:** "Generate Cover Letter" amber button on preview page (hidden after generation)

---

### Module 27 — Cover Letter Enhancement Layer

Transforms the structured cover letter draft into stronger, more professional language.

**File:** `app/utils/cover_letter_enhancer.py`

**Function:** `enhance_cover_letter(cover_letter_draft, enhanced_resume)`

**Returns:** dict with `recipient`, `company`, `target_title`, `enhanced_opening`, `enhanced_body`, `enhanced_closing`, `full_text`

**Route:** `GET /enhance-cover-letter` — enhances draft, stores in session, redirects to preview

**UI:** "Enhance Cover Letter" purple button (shown only when draft exists but not yet enhanced); "ENHANCED" badge on cover letter section

---

### Module 28 — Resume + Cover Letter Paired Export

Downloads a combined application package as a single .txt file.

**Route:** `GET /download-application-package`

**Output:** Plain-text file with Section 1 (Resume) and Section 2 (Cover Letter), using enhanced versions when available.

**UI:** "Download Application Package" teal button on preview page (shown when cover letter exists)

---

### Module 29 — Saved Application Package View

Save and manage combined resume + cover letter packages per session.

**File:** `app/utils/application_package.py`

**Functions:**

- `save_package(session_data)` — snapshots report_data, enhanced_resume, cover_letter_draft, enhanced_cover_letter
- `load_package(package)` — returns deep copies of all four data objects
- `find_package(packages, package_id)` / `delete_package(packages, package_id)`

**Routes:**

- `GET /save-application-package` — saves current state as a package
- `GET /application-package/<id>` — loads a saved package into active session
- `GET /application-package/<id>/download` — downloads saved package directly
- `GET /delete-application-package/<id>` — removes a saved package

**UI:**

- "Save Application Package" button on preview page (when cover letter exists)
- Saved Application Packages panel on dashboard and preview page with Open, Download, Delete actions
- Labels derived from target title; company shown if available

**Behavior:**

- Session-based, no database
- Deep copies prevent cross-package contamination
- Duplicates allowed, distinguished by timestamp
- Opening a package restores resume, cover letter, and enhancement state
- Existing resume-only flow works unchanged when no cover letter or packages exist

---

### Module 30 — Match Score Explanation Panel

Explains the match score in plain English.

**File:** `app/utils/match_explainer.py`

**Function:** `explain_match(match, profile, tailored, rewrite)`

**Returns:** `score`, `strengths`, `gaps`, `summary`, `confidence_note`

---

### Module 31 — Missing Keyword Gap Detector

Surfaces missing or underrepresented keywords that could improve fit.

**File:** `app/utils/keyword_gap_detector.py`

**Function:** `detect_keyword_gaps(match, tailored, rewrite, profile)`

**Returns:** `missing_keywords`, `underused_keywords`, `recommended_additions`

---

### Module 32 — Priority Fixes / Quick Wins

Identifies the fastest actions to improve resume-job fit.

**File:** `app/utils/priority_fixes.py`

**Function:** `generate_priority_fixes(match, profile, tailored, rewrite, scorecard)`

**Returns:** `top_priority`, `quick_wins`, `section_targets`

---

### Module 33 — Role-Fit Improvement Suggestions

Strategic suggestions for improving fit for the target role.

**File:** `app/utils/role_fit_suggestions.py`

**Function:** `suggest_role_fit(match, profile, tailored, rewrite, enhanced_resume)`

**Returns:** `target_title`, `fit_level`, `improvement_suggestions`, `positioning_advice`, `next_step`

---

**M30-M33 Integration:**

- Intelligence is generated automatically after analysis and stored in session
- Refreshed when loading saved versions or application packages
- Panels appear on both dashboard and preview page
- Hidden when no match data exists
- All logic is deterministic — no AI APIs

---

### Module 34 — Saved Jobs Tracker

Track target jobs within your session.

**File:** `app/utils/job_tracker.py`

**Functions:** `create_saved_job()`, `update_job_status()`, `find_job()`, `delete_job()`

**Routes:** `GET /save-job`, `GET /job/<job_id>`, `GET /delete-job/<job_id>`

---

### Module 35 — Application Status Tracker

Move saved jobs through the application funnel.

**Statuses:** Saved → Preparing → Applied → Follow-Up → Interview → Offer → Rejected

**Route:** `GET /job/<job_id>/status/<new_status>`

---

### Module 36 — Alerts Foundation

Session-based reminders tied to saved jobs.

**File:** `app/utils/alerts.py`

**Functions:** `create_alert()`, `complete_alert()`, `delete_alert()`, `get_active_alerts()`

**Routes:** `GET /create-followup-alert/<job_id>`, `GET /complete-alert/<alert_id>`, `GET /delete-alert/<alert_id>`

---

### Module 37 — Follow-Up / Reminder Prompts

Status-based recommended actions, message templates, and next steps.

**File:** `app/utils/followup_prompts.py`

**Function:** `generate_followup_prompts(job)`

**Returns:** `job_id`, `status`, `recommended_actions`, `message_templates`, `next_step`

---

**M34-M37 Integration:**

- Saved Jobs panel appears on dashboard and preview page
- Job detail page shows status controls, follow-up prompts, and alerts
- Alerts panel shows upcoming reminders (hidden when empty)
- Follow-up prompts update dynamically based on job status
- Session-based only — no database, no external integrations
- Existing resume/application flow remains fully intact

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
