"""M69 — Job Data Model (MVP). Static dataset of realistic job listings."""

JOBS = [
    {
        "id": "job_1",
        "title": "Backend Engineer",
        "company": "TechCorp",
        "location": "Remote",
        "skills": ["python", "flask", "api", "sql", "docker"],
        "description": "Build APIs and backend systems for a growing SaaS platform.",
    },
    {
        "id": "job_2",
        "title": "Frontend Developer",
        "company": "PixelWorks",
        "location": "New York, NY",
        "skills": ["javascript", "react", "css", "html", "typescript"],
        "description": "Create responsive user interfaces and improve UX across web apps.",
    },
    {
        "id": "job_3",
        "title": "Data Analyst",
        "company": "InsightHub",
        "location": "Remote",
        "skills": ["python", "sql", "excel", "tableau", "statistics"],
        "description": "Analyze business data, build dashboards, and deliver actionable insights.",
    },
    {
        "id": "job_4",
        "title": "Full Stack Developer",
        "company": "LaunchPad Inc",
        "location": "San Francisco, CA",
        "skills": ["python", "javascript", "react", "flask", "sql", "api"],
        "description": "Build end-to-end features across frontend and backend systems.",
    },
    {
        "id": "job_5",
        "title": "DevOps Engineer",
        "company": "CloudNine",
        "location": "Remote",
        "skills": ["docker", "kubernetes", "aws", "ci/cd", "linux", "python"],
        "description": "Manage cloud infrastructure, CI/CD pipelines, and deployment automation.",
    },
    {
        "id": "job_6",
        "title": "Data Scientist",
        "company": "Predictive Labs",
        "location": "Boston, MA",
        "skills": ["python", "machine learning", "sql", "statistics", "pandas", "tensorflow"],
        "description": "Build predictive models and run experiments to drive product decisions.",
    },
    {
        "id": "job_7",
        "title": "Product Manager",
        "company": "BuildRight",
        "location": "Austin, TX",
        "skills": ["product strategy", "agile", "analytics", "roadmapping", "stakeholder management"],
        "description": "Define product vision, prioritize features, and work with engineering teams.",
    },
    {
        "id": "job_8",
        "title": "Marketing Manager",
        "company": "GrowthEngine",
        "location": "Remote",
        "skills": ["digital marketing", "seo", "analytics", "content strategy", "social media"],
        "description": "Plan and execute marketing campaigns to drive user acquisition and retention.",
    },
    {
        "id": "job_9",
        "title": "UX Designer",
        "company": "DesignFirst",
        "location": "Seattle, WA",
        "skills": ["figma", "user research", "wireframing", "prototyping", "css"],
        "description": "Design intuitive user experiences through research, prototyping, and testing.",
    },
    {
        "id": "job_10",
        "title": "Business Analyst",
        "company": "StratCo",
        "location": "Chicago, IL",
        "skills": ["sql", "excel", "requirements analysis", "stakeholder management", "reporting"],
        "description": "Gather requirements, analyze workflows, and bridge business and technology teams.",
    },
    {
        "id": "job_11",
        "title": "Machine Learning Engineer",
        "company": "AI Dynamics",
        "location": "Remote",
        "skills": ["python", "machine learning", "tensorflow", "docker", "api", "sql"],
        "description": "Deploy and optimize ML models in production environments.",
    },
    {
        "id": "job_12",
        "title": "Software Engineer",
        "company": "CoreStack",
        "location": "Denver, CO",
        "skills": ["python", "java", "api", "sql", "git", "testing"],
        "description": "Design and implement scalable software solutions across the stack.",
    },
    {
        "id": "job_13",
        "title": "QA Engineer",
        "company": "QualityFirst",
        "location": "Remote",
        "skills": ["testing", "selenium", "python", "api", "ci/cd"],
        "description": "Develop automated test suites and ensure product quality before release.",
    },
    {
        "id": "job_14",
        "title": "Content Strategist",
        "company": "WordCraft",
        "location": "Portland, OR",
        "skills": ["content strategy", "seo", "copywriting", "analytics", "social media"],
        "description": "Develop and manage content programs that drive engagement and growth.",
    },
    {
        "id": "job_15",
        "title": "Project Manager",
        "company": "DeliverNow",
        "location": "Remote",
        "skills": ["project management", "agile", "stakeholder management", "risk management", "reporting"],
        "description": "Lead cross-functional projects from planning through delivery.",
    },
    {
        "id": "job_16",
        "title": "Cloud Architect",
        "company": "SkyBridge Tech",
        "location": "Remote",
        "skills": ["aws", "azure", "kubernetes", "docker", "networking", "security"],
        "description": "Design scalable cloud architectures and guide migration strategies.",
    },
    {
        "id": "job_17",
        "title": "Sales Operations Analyst",
        "company": "RevOps Co",
        "location": "New York, NY",
        "skills": ["salesforce", "excel", "sql", "reporting", "analytics"],
        "description": "Optimize sales processes, maintain CRM data, and produce pipeline reports.",
    },
    {
        "id": "job_18",
        "title": "Mobile Developer",
        "company": "AppForge",
        "location": "Los Angeles, CA",
        "skills": ["react native", "javascript", "typescript", "api", "git"],
        "description": "Build and maintain cross-platform mobile applications.",
    },
]


def get_all_jobs():
    """Return the full list of job listings."""
    return JOBS


def find_job_by_id(job_id):
    """Return a single job dict by ID, or None."""
    return next((j for j in JOBS if j["id"] == job_id), None)
