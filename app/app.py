from dotenv import load_dotenv
load_dotenv()

import os
import pandas as pd
import psycopg2
import psycopg2.errors
import streamlit as st

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


jobs = query("SELECT job_id, title FROM jobs ORDER BY title")
titles = dict(zip(jobs.job_id, jobs.title))

page = st.sidebar.radio("Page", ["Pipeline", "Add candidate", "Add job", "History"])

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
    with st.form("add"):
        name = st.text_input("Full name")
        name_ar = st.text_input("Name (Arabic)")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        job = st.selectbox("Job", list(titles), format_func=titles.get)
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
                    "INSERT INTO applications (candidate_id, job_id, source) VALUES (%s, %s, %s)",
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
    recruiters = query("SELECT recruiter_id, full_name FROM recruiters ORDER BY full_name")
    rec_names = dict(zip(recruiters.recruiter_id, recruiters.full_name))
    with st.form("add_job"):
        title = st.text_input("Job title")
        title_ar = st.text_input("Job title (Arabic)")
        department = st.text_input("Department")
        rec = st.selectbox("Recruiter", list(rec_names), format_func=rec_names.get)
        submitted = st.form_submit_button("Add job")

    if submitted:
        if not title.strip():
            st.error("Job title is required.")
        else:
            try:
                execute(
                    """INSERT INTO jobs (title, title_ar, department, recruiter_id)
                       VALUES (%s, %s, %s, %s)""",
                    (title.strip(), title_ar or None, department or None, int(rec)),
                )
                st.success("Job added. Open the Pipeline page to see it.")
            except psycopg2.Error as e:
                st.error(e.pgerror or str(e))

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