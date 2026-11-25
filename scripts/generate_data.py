import os
import random
from datetime import datetime, timedelta, timezone

import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

first_names = [("Omar", "عمر"), ("Sara", "سارة"), ("Layla", "ليلى"), ("Yousef", "يوسف"),
               ("Maryam", "مريم"), ("Khaled", "خالد"), ("Noor", "نور"), ("Ali", "علي")]
last_names = [("Haddad", "حداد"), ("Mansour", "منصور"), ("Nasser", "ناصر"),
              ("Saleh", "صالح"), ("Darwish", "درويش"), ("Rashid", "راشد")]
jobs = [("Customer Support Specialist", "أخصائي دعم العملاء", "Support"),
        ("Account Manager", "مدير حساب", "Sales"),
        ("HR Coordinator", "منسق موارد بشرية", "HR"),
        ("Sales Representative", "مندوب مبيعات", "Sales"),
        ("Operations Coordinator", "منسق عمليات", "Operations")]
sources = ["linkedin"] * 4 + ["indeed"] * 3 + ["referral"] * 2 + ["company_site"] * 2 + ["other"]

# Recruiters and jobs
for i, name in enumerate(["Lina Haddad", "Faisal Nasser", "Mona Saleh", "Rami Darwish"]):
    cur.execute("INSERT INTO recruiters (full_name, email) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (name, f"recruiter{i}@example.com"))
cur.execute("SELECT recruiter_id FROM recruiters")
recruiter_ids = [r[0] for r in cur.fetchall()]

for title, title_ar, dept in jobs:
    cur.execute("INSERT INTO jobs (title, title_ar, department, recruiter_id) VALUES (%s, %s, %s, %s)",
                (title, title_ar, dept, random.choice(recruiter_ids)))
cur.execute("SELECT job_id FROM jobs")
job_ids = [r[0] for r in cur.fetchall()]

# Candidates
now = datetime.now(timezone.utc)
for i in range(150):
    fe, fa = random.choice(first_names)
    le, la = random.choice(last_names)
    applied = now - timedelta(days=random.randint(60, 120))

    cur.execute("""INSERT INTO candidates (full_name, full_name_ar, email, phone, created_at)
                   VALUES (%s, %s, %s, %s, %s) RETURNING candidate_id""",
                (f"{fe} {le}", f"{fa} {la}", f"{fe}.{le}{i}@example.com".lower(),
                 f"+965{random.randint(50000000, 69999999)}", applied))
    candidate_id = cur.fetchone()[0]

    cur.execute("""INSERT INTO applications (candidate_id, job_id, source, applied_at)
                   VALUES (%s, %s, %s, %s) RETURNING application_id""",
                (candidate_id, random.choice(job_ids), random.choice(sources), applied))
    app_id = cur.fetchone()[0]

    # Where this application ends: 1-5 = reached that stage, 6 = rejected
    final = random.choice([1, 2, 2, 3, 3, 4, 5, 5, 6, 6])
    if final == 6:
        path = list(range(2, random.randint(1, 4) + 1)) + [6]   # rejected after some stages
    else:
        path = list(range(2, final + 1))

    # Backdate the first history row, then move step by step so the trigger logs each one
    when = applied
    cur.execute("UPDATE application_stage_history SET changed_at = %s WHERE application_id = %s",
                (when, app_id))
    for stage in path:
        when += timedelta(days=random.randint(1, 10))
        cur.execute("UPDATE applications SET current_stage_id = %s WHERE application_id = %s",
                    (stage, app_id))
        cur.execute("""UPDATE application_stage_history SET changed_at = %s
                       WHERE application_id = %s AND to_stage_id = %s""", (when, app_id, stage))

conn.commit()
print("Done: 150 candidates inserted.")