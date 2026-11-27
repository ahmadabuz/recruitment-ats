-- Rules for closing jobs and preventing duplicate postings.
-- Run after 01_schema.sql, 02_triggers.sql and 03_seed_minimal.sql.
-- Note: in the Neon SQL Editor, run each statement separately.

-- Department is required
ALTER TABLE jobs ALTER COLUMN department SET NOT NULL;

-- A closed job must have a closing date
ALTER TABLE jobs ADD CONSTRAINT closed_has_date
    CHECK (status <> 'closed' OR closed_at IS NOT NULL);

-- Only one OPEN job per title (case-insensitive).
-- Closed jobs don't count, so a role can be reopened later.
CREATE UNIQUE INDEX uq_open_job
    ON jobs (lower(title))
    WHERE status = 'open';

-- No new applications to jobs that aren't open
CREATE OR REPLACE FUNCTION block_closed_job_applications() RETURNS trigger AS $$
BEGIN
    IF (SELECT status FROM jobs WHERE job_id = NEW.job_id) <> 'open' THEN
        RAISE EXCEPTION 'Job % is not open for applications', NEW.job_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_block_closed_job
BEFORE INSERT ON applications
FOR EACH ROW EXECUTE FUNCTION block_closed_job_applications();