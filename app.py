import os
import yaml
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from agent.profile import CandidateProfile
from agent.orchestrator import JobAgent
from storage.database import upsert_job, all_jobs, update_status

load_dotenv()
st.set_page_config(page_title="AI Job Application Agent", page_icon="🎯", layout="wide")
st.title("🎯 AI Agentic Job Application Assistant")
st.caption("Discover · Match · Review · Prepare · Track | Approval mode: ON")

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)
threshold = int(os.getenv("MIN_MATCH_SCORE", config["agent"]["minimum_match_score"]))

with st.sidebar:
    st.header("Agent configuration")
    st.metric("Minimum match score", f"{threshold}%")
    st.write("Experience target: **7–10 years**")
    st.write("Roles: Senior DV, SoC DV, IP DV, Lead DV")
    st.info("No application is submitted automatically. You review and submit.")

profile_tab, shortlist_tab, tracker_tab = st.tabs(["My profile & import", "Strong matches", "Application tracker"])

with profile_tab:
    st.subheader("Candidate profile")
    uploaded = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])
    if uploaded:
        from utils.text_extract import extract_resume
        temp_path = os.path.join("/tmp", uploaded.name)
        with open(temp_path, "wb") as f: f.write(uploaded.getbuffer())
        resume_text = extract_resume(temp_path)
    else:
        resume_text = open("data/profile.txt", encoding="utf-8").read()
    resume_text = st.text_area("Review/edit profile text", resume_text, height=180)

    st.subheader("Import jobs")
    csv_upload = st.file_uploader("Upload job listings CSV", type=["csv"], key="jobs_csv")
    jobs = pd.read_csv(csv_upload).fillna("").to_dict("records") if csv_upload else []
    with st.expander("Or add one job manually"):
        title = st.text_input("Job title")
        company = st.text_input("Company")
        location = st.text_input("Location")
        url = st.text_input("Job posting URL")
        description = st.text_area("Job description")
        if st.button("Add job"):
            jobs.append({"title": title, "company": company, "location": location,
                        "url": url, "description": description, "source": "Manual"})
            st.success("Job added to this session. Click Analyze below.")
    if st.button("Analyze and score jobs", type="primary", disabled=not jobs):
        profile = CandidateProfile.from_text(resume_text, config)
        profile.years_experience = 9.0  # Update from your actual resume if different.
        ranked = JobAgent(profile, threshold).evaluate(jobs)
        st.session_state["ranked_jobs"] = ranked
        for job in ranked:
            if job.get("url"):
                upsert_job(job)
        st.success(f"Analyzed {len(ranked)} jobs; {sum(j['eligible'] for j in ranked)} meet threshold.")

with shortlist_tab:
    ranked = st.session_state.get("ranked_jobs", [])
    if not ranked:
        st.info("Import jobs and run analysis in the first tab.")
    for j in ranked:
        m = j["match"]
        if not j["eligible"]: continue
        with st.container(border=True):
            st.subheader(f"{j.get('title','Role')} — {j.get('company','Company')}")
            st.write(f"{j.get('location','')} | **Match: {m.score}%**")
            st.progress(m.score / 100)
            st.caption(m.explanation)
            st.write("Matched:", ", ".join(m.matched_skills) or "No verified skills detected")
            st.write("Possible gaps:", ", ".join(m.missing_skills[:10]) or "None detected")
            if j.get("url"): st.markdown(f"[Open job posting]({j['url']})")
            st.warning("Review role, location, requirements and resume accuracy before applying.")
            if st.button("Mark as Prepared", key=f"prep_{j.get('url','')}_{j.get('title','')}"):
                if j.get("url"): update_status(j["url"], "Prepared")
                st.toast("Status updated. Final application submission remains manual.")

with tracker_tab:
    records = all_jobs()
    if records:
        df = pd.DataFrame(records)
        st.dataframe(df[["title","company","location","score","status","url","created_at"]],
                     use_container_width=True)
        chosen_url = st.selectbox("Job to update", df["url"].tolist())
        status = st.selectbox("Status", ["Shortlisted","Prepared","Applied","Interview","Rejected","Offer","Withdrawn","Not suitable"])
        notes = st.text_input("Notes")
        if st.button("Save status"):
            update_status(chosen_url, status, notes)
            st.success("Saved.")
    else:
        st.info("Your tracked jobs will appear here after analysis.")
