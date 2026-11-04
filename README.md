# Agentic Job Application Assistant
Approval-first job matching and application tracker. Minimum match score: 75%. Target experience: 7–10 years.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# WSL/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Upload your resume and jobs CSV. Analyze, review matches, then open job links and submit manually.

## Safety
This version does not scrape LinkedIn behind login, bypass CAPTCHA, or auto-submit. Use authorized job feeds/exports and manually review applications. Never commit resumes, API keys, or database files.
