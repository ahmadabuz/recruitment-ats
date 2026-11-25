CREATE TABLE recruiters (
    recruiter_id SERIAL PRIMARY KEY,
    full_name    TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE
);

CREATE TABLE stages (
    stage_id   SMALLINT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    sort_order SMALLINT NOT NULL UNIQUE
);

INSERT INTO stages (stage_id, name, sort_order) VALUES
    (1, 'Applied', 1),
    (2, 'Screening', 2),
    (3, 'Interview', 3),
    (4, 'Offer', 4),
    (5, 'Hired', 5),
    (6, 'Rejected', 6);

CREATE TABLE candidates (
    candidate_id SERIAL PRIMARY KEY,
    full_name    TEXT NOT NULL,
    full_name_ar TEXT,
    email        TEXT NOT NULL,
    phone        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT email_format CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$') -- duplicate-proof email
);

CREATE UNIQUE INDEX uq_candidates_email ON candidates (lower(email));


CREATE TABLE jobs (
    job_id       SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    title_ar     TEXT,
    department   TEXT,
    recruiter_id INT NOT NULL REFERENCES recruiters(recruiter_id),
    status       TEXT NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'closed', 'on_hold')),
    opened_at    DATE NOT NULL DEFAULT CURRENT_DATE,
    closed_at    DATE,
    CONSTRAINT closed_after_open
        CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

-- (one candidate can apply to a job only once)
CREATE TABLE applications (
    application_id   SERIAL PRIMARY KEY,
    candidate_id     INT NOT NULL REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    job_id           INT NOT NULL REFERENCES jobs(job_id),
    source           TEXT NOT NULL
                     CHECK (source IN ('linkedin','indeed','referral','company_site','other')),
    current_stage_id SMALLINT NOT NULL DEFAULT 1 REFERENCES stages(stage_id),
    applied_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, job_id)
);

-- audit trail (filled automatically by the trigger)
CREATE TABLE application_stage_history (
    history_id     BIGSERIAL PRIMARY KEY,
    application_id INT NOT NULL REFERENCES applications(application_id) ON DELETE CASCADE,
    from_stage_id  SMALLINT REFERENCES stages(stage_id),
    to_stage_id    SMALLINT NOT NULL REFERENCES stages(stage_id),
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_applications_job ON applications(job_id);
CREATE INDEX idx_history_app_time ON application_stage_history(application_id, changed_at);