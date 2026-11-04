import os, re, sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="AI Agentic Job Application Assistant", page_icon="🎯", layout="wide")
st.title("🎯 AI Agentic Job Application Assistant")
st.caption("Discover • Match • Review • Prepare • Track | Approval mode: ON")

DEFAULT_CONFIG = {"agent": {
"minimum_match_score":75, "experience_min_years":7, "experience_max_years":10,
"locations":["Bengaluru","Hyderabad","Pune","Noida","Ahmedabad","Remote","India"],
"target_titles":["Senior Design Verification Engineer","SoC Design Verification Engineer","IP Verification Engineer","Lead Design Verification Engineer","Design Verification Engineer"],
"core_skills":["SystemVerilog","UVM","SVA","functional coverage","constrained random","scoreboard","PCIe","AXI","AHB","USB","I2C","SPI","VCS","Questa","Verdi","SoC verification","IP verification","debug"]}}

def read_config():
    try:
        with open("config.yaml",encoding="utf-8") as f: c=yaml.safe_load(f)
        return c if isinstance(c,dict) and "agent" in c else DEFAULT_CONFIG
    except Exception: return DEFAULT_CONFIG
CFG=read_config()["agent"]
THRESHOLD=int(os.getenv("MIN_MATCH_SCORE",CFG.get("minimum_match_score",75)))
DB=os.getenv("DATABASE_PATH","data/applications.db")
Path(DB).parent.mkdir(parents=True,exist_ok=True)

def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,company TEXT,location TEXT,description TEXT,requirements TEXT,url TEXT UNIQUE,source TEXT,score INTEGER DEFAULT 0,status TEXT DEFAULT 'Shortlisted',notes TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.commit(); return c
def save_job(j,score):
    if not j.get("url"): return
    c=connect()
    c.execute("""INSERT INTO jobs(title,company,location,description,requirements,url,source,score,status,notes) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET score=excluded.score""",
    (str(j.get("title","")),str(j.get("company","")),str(j.get("location","")),str(j.get("description","")),str(j.get("requirements","")),str(j.get("url","")),str(j.get("source","CSV")),int(score),"Shortlisted",""))
    c.commit(); c.close()
def get_jobs():
    c=connect(); rows=c.execute("SELECT * FROM jobs ORDER BY score DESC,created_at DESC").fetchall(); c.close()
    return [dict(r) for r in rows]
def set_status(url,status,notes):
    c=connect(); c.execute("UPDATE jobs SET status=?,notes=? WHERE url=?",(status,notes,url)); c.commit(); c.close()
def norm(x): return re.sub(r"[^a-z0-9+#. ]"," ",str(x or "").lower())

def extract_resume(f):
    if not f: return ""
    raw=f.getvalue(); name=f.name.lower()
    if name.endswith(".txt"): return raw.decode("utf-8",errors="ignore")
    import io
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(raw)).pages)
    if name.endswith(".docx"):
        from docx import Document
        return "\n".join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
    return ""

def score(j,resume,years):
    skills=CFG.get("core_skills",DEFAULT_CONFIG["agent"]["core_skills"])
    found=[s for s in skills if re.search(re.escape(s),resume,re.I)]
    jd=norm(" ".join([j.get("title",""),j.get("description",""),j.get("requirements","")]))
    matched=[s for s in found if norm(s) in jd]; gaps=[s for s in found if s not in matched]
    ss=100*len(matched)/max(1,len(found))
    title=norm(j.get("title","")); targets=[norm(t) for t in CFG.get("target_titles",[])]
    ts=100 if any(t and (t in title or title in t) for t in targets) else (75 if "verification engineer" in title or "dv engineer" in title else 35)
    try:
        lo=float(j.get("experience_min") or 7); hi=float(j.get("experience_max") or 10)
        es=100 if lo<=years<=hi else max(0,100-15*min(abs(years-lo),abs(years-hi)))
    except (TypeError,ValueError): es=75
    loc=norm(j.get("location","")); locations=CFG.get("locations",[])
    ls=100 if any(norm(x) in loc for x in locations) else (70 if "india" in loc or "remote" in loc else 45)
    total=round(.5*ss+.2*ts+.2*es+.1*ls)
    return {"score":total,"matched":matched,"gaps":gaps,"explanation":f"Skills {ss:.0f}% • Role {ts:.0f}% • Experience {es:.0f}% • Location {ls:.0f}%"}

with st.sidebar:
    st.header("Agent settings"); st.metric("Minimum match score",f"{THRESHOLD}%")
    years=st.number_input("Your relevant experience (years)",0.0,40.0,9.0,0.5)
    st.write("Target experience: **7–10 years**")
    st.info("Approval mode ON. No applications are submitted automatically.")

a,b,c=st.tabs(["Profile & import","Strong matches","Application tracker"])
with a:
    st.subheader("Resume")
    upload=st.file_uploader("Upload PDF, DOCX or TXT resume",type=["pdf","docx","txt"])
    resume=extract_resume(upload)
    resume=st.text_area("Extracted / pasted resume text (please verify)",resume,height=210,placeholder="Or paste resume text here")
    st.subheader("Import job listings")
    csv=st.file_uploader("Upload CSV (title, company, location, description, requirements, url, source, experience_min, experience_max)",type=["csv"],key="csvjobs")
    jobs=[]
    if csv:
        try:
            jobs=pd.read_csv(csv).fillna("").to_dict("records"); st.success(f"Loaded {len(jobs)} jobs"); st.dataframe(pd.DataFrame(jobs).head(5),use_container_width=True)
        except Exception as e: st.error(f"CSV read error: {e}")
    with st.expander("Add one job manually"):
        manual={"title":st.text_input("Title"),"company":st.text_input("Company"),"location":st.text_input("Location"),"url":st.text_input("Job URL"),"description":st.text_area("Description"),"requirements":st.text_area("Requirements"),"source":"Manual"}
        if st.button("Add manual job"):
            if manual["title"] and (manual["description"] or manual["requirements"]):
                st.session_state.setdefault("manual",[]).append(manual); st.success("Added to this session")
            else: st.warning("Add title and description/requirements")
    jobs+=st.session_state.get("manual",[])
    if st.button("Analyze and score jobs",type="primary",disabled=not jobs):
        if not resume.strip(): st.warning("Upload or paste your resume first.")
        else:
            ranked=[]
            for j in jobs:
                r=score(j,resume,years); item=dict(j); item["result"]=r; item["eligible"]=r["score"]>=THRESHOLD
                ranked.append(item); save_job(item,r["score"])
            ranked.sort(key=lambda x:x["result"]["score"],reverse=True)
            st.session_state["ranked"]=ranked
            st.success(f"Analyzed {len(ranked)} jobs; {sum(x['eligible'] for x in ranked)} meet threshold.")
with b:
    ranked=st.session_state.get("ranked",[])
    if not ranked: st.info("Import jobs and analyze them in the first tab.")
    else:
        qualified=[j for j in ranked if j["eligible"]]; st.subheader(f"{len(qualified)} jobs match {THRESHOLD}%+")
        for i,j in enumerate(qualified):
            r=j["result"]
            with st.container(border=True):
                st.subheader(f"{j.get('title','Role')} — {j.get('company','Company')}")
                st.write(f"{j.get('location','')} | **Match: {r['score']}%**"); st.progress(r["score"]/100); st.caption(r["explanation"])
                st.write("Matched skills: "+(", ".join(r["matched"]) or "None detected"))
                st.write("Potential gaps: "+(", ".join(r["gaps"][:12]) or "None detected"))
                if j.get("url"): st.link_button("Open job posting",j["url"])
                st.warning("Review requirements and resume accuracy. Submit application yourself.")
                if st.button("Mark Prepared",key=f"prepared_{i}"):
                    if j.get("url"): set_status(j["url"],"Prepared","Reviewed in app")
                    st.toast("Status updated.")
with c:
    rows=get_jobs()
    if not rows: st.info("Analyzed jobs will appear here.")
    else:
        st.dataframe(pd.DataFrame(rows),use_container_width=True)
        urls=[x["url"] for x in rows if x.get("url")]
        if urls:
            u=st.selectbox("Choose job URL",urls)
            status=st.selectbox("Update status",["Shortlisted","Prepared","Applied","Interview","Rejected","Offer","Withdrawn","Not suitable"])
            notes=st.text_input("Notes")
            if st.button("Save tracker update"): set_status(u,status,notes); st.success("Saved.")
