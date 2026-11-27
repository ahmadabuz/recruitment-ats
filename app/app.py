from dotenv import load_dotenv
load_dotenv()

import os
import warnings

import pandas as pd
import psycopg2
import psycopg2.errors
import streamlit as st

warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

st.set_page_config(page_title="Recruitment ATS", layout="wide")


def conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def query(sql, params=None):
    with conn() as c:
        return pd.read_sql(sql, c, params=params)


def execute(sql, params=None):
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params)


def move(app_id, stage_id):
    try:
        execute(
            "UPDATE applications SET current_stage_id = %s WHERE application_id = %s",
            (stage_id, app_id),
        )
        st.rerun()
    except psycopg2.Error as e:
        st.error(e.pgerror or str(e))


def set_job_status(job_id, status):
    try:
        if status == "closed":
            execute(
                "UPDATE jobs SET status = 'closed', closed_at = CURRENT_DATE "
                "WHERE job_id = %s",
                (int(job_id),),
            )
        else:
            execute(
                "UPDATE jobs SET status = 'open', closed_at = NULL WHERE job_id = %s",
                (int(job_id),),
            )
        st.rerun()
    except psycopg2.Error as e:
        st.error(e.pgerror or str(e))


jobs = query("SELECT job_id, title, status FROM jobs ORDER BY status, title")
titles = {
    r.job_id: r.title + ("" if r.status == "open" else " (closed)")
    for r in jobs.itertuples()
}
open_titles = {r.job_id: r.title for r in jobs.itertuples() if r.status == "open"}

page = st.sidebar.radio(
    "Page", ["Pipeline", "Add candidate", "Add job", "Manage jobs", "History"]
)

if page == "Pipeline":
    st.title("Hiring pipeline")
    job = st.selectbox("Job", list(titles), format_func=titles.get)
    stages = query("SELECT stage_id, name FROM stages ORDER BY sort_order")
    apps = query(
        """SELECT a.application_id, c.full_name, c.full_name_ar, a.source,
                  s.name AS stage, a.current_stage_id
           FROM applications a
           JOIN candidates c USING (candidate_id)
           JOIN stages s ON s.stage_id = a.current_stage_id
           WHERE a.job_id = %s
           ORDER BY a.current_stage_id, c.full_name""",
        (int(job),),
    )

    for col, (_, s) in zip(st.columns(len(stages)), stages.iterrows()):
        col.metric(s["name"], int((apps.current_stage_id == s["stage_id"]).sum()))

    st.divider()
    for _, r in apps.iterrows():
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
        name_ar = r.full_name_ar if pd.notna(r.full_name_ar) else ""
        c1.write(f"{r.full_name}  {name_ar}")
        c2.write(r.source)
        c3.write(r.stage)
        if r.current_stage_id < 5:
            if c4.button("Advance", key=f"adv{r.application_id}"):
                move(r.application_id, r.current_stage_id + 1)
            if c5.button("Reject", key=f"rej{r.application_id}"):
                move(r.application_id, 6)

elif page == "Add candidate":
    st.title("Add candidate")
    if not open_titles:
        st.warning("There are no open jobs. Add or reopen a job first.")
    else:
        with st.form("add"):
            name = st.text_input("Full name")
            name_ar = st.text_input("Name (Arabic)")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            job = st.selectbox("Job", list(open_titles), format_func=open_titles.get)
            source = st.selectbox(
                "Source", ["linkedin", "indeed", "referral", "company_site", "other"]
            )
            submitted = st.form_submit_button("Add")

        if submitted:
            try:
                with conn() as c, c.cursor() as cur:
                    cur.execute(
                        """INSERT INTO candidates (full_name, full_name_ar, email, phone)
                           VALUES (%s, %s, %s, %s) RETURNING candidate_id""",
                        (name, name_ar or None, email, phone or None),
                    )
                    cid = cur.fetchone()[0]
                    cur.execute(
                        "INSERT INTO applications (candidate_id, job_id, source) "
                        "VALUES (%s, %s, %s)",
                        (cid, int(job), source),
                    )
                st.success("Candidate added")
            except psycopg2.errors.UniqueViolation:
                st.error("A candidate with this email already exists.")
            except psycopg2.errors.CheckViolation:
                st.error("Invalid email format.")
            except psycopg2.Error as e:
                st.error(e.pgerror or str(e))

elif page == "Add job":
    st.title("Add job")
    recruiters = query(
        "SELECT recruiter_id, full_name FROM recruiters ORDER BY full_name"
    )
    rec_names = dict(zip(recruiters.recruiter_id, recruiters.full_name))
    with st.form("add_job"):
        title = st.text_input("Job title")
        title_ar = st.text_input("Job title (Arabic)")
        department = st.text_input("Department")
        rec = st.selectbox("Recruiter", list(rec_names), format_func=rec_names.get)
        submitted = st.form_submit_button("Add job")

    if submitted:
        if not title.strip() or not department.strip():
            st.error("Job title and department are required.")
        else:
            try:
                execute(
                    """INSERT INTO jobs (title, title_ar, department, recruiter_id)
                       VALUES (%s, %s, %s, %s)""",
                    (title.strip(), title_ar or None, department.strip() or None, int(rec)),
                )
                st.success("Job added. Open the Pipeline page to see it.")
            except psycopg2.errors.UniqueViolation:
                st.error("An open job with this title already exists.")
            except psycopg2.Error as e:
                st.error(e.pgerror or str(e))

elif page == "Manage jobs":
    st.title("Manage jobs")
    all_jobs = query(
        """SELECT j.job_id, j.title, j.department, j.status,
                  COUNT(a.application_id) AS applications
           FROM jobs j LEFT JOIN applications a USING (job_id)
           GROUP BY j.job_id
           ORDER BY j.status, j.title"""
    )
    for _, r in all_jobs.iterrows():
        c1, c2, c3 = st.columns([4, 3, 1])
        dept = r.department if pd.notna(r.department) else "-"
        c1.write(f"{r.title} ({dept})")
        c2.write(f"{r.status} · {r.applications} applications")
        if r.status == "open":
            if c3.button("Close", key=f"close{r.job_id}"):
                set_job_status(r.job_id, "closed")
        else:
            if c3.button("Reopen", key=f"open{r.job_id}"):
                set_job_status(r.job_id, "open")

else:
    st.title("Stage history")
    st.dataframe(
        query(
            """SELECT h.changed_at, c.full_name, j.title AS job,
                      fs.name AS from_stage, ts.name AS to_stage
               FROM application_stage_history h
               JOIN applications a USING (application_id)
               JOIN candidates c USING (candidate_id)
               JOIN jobs j USING (job_id)
               LEFT JOIN stages fs ON fs.stage_id = h.from_stage_id
               JOIN stages ts ON ts.stage_id = h.to_stage_id
               ORDER BY h.changed_at DESC"""
        )
    )