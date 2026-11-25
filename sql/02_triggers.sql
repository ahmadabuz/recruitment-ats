CREATE OR REPLACE FUNCTION log_stage_change() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO application_stage_history (application_id, from_stage_id, to_stage_id)
        VALUES (NEW.application_id, NULL, NEW.current_stage_id);

    ELSIF NEW.current_stage_id <> OLD.current_stage_id THEN
        -- Hired and Rejected are final
        IF OLD.current_stage_id IN (5, 6) THEN
            RAISE EXCEPTION 'Application % is already closed', OLD.application_id;
        END IF;

        -- Only one step forward, or reject from any open stage
        IF NEW.current_stage_id <> 6 AND
           (SELECT sort_order FROM stages WHERE stage_id = NEW.current_stage_id) <>
           (SELECT sort_order FROM stages WHERE stage_id = OLD.current_stage_id) + 1 THEN
            RAISE EXCEPTION 'Invalid stage move: % -> %', OLD.current_stage_id, NEW.current_stage_id;
        END IF;

        INSERT INTO application_stage_history (application_id, from_stage_id, to_stage_id)
        VALUES (NEW.application_id, OLD.current_stage_id, NEW.current_stage_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_stage_change
AFTER INSERT OR UPDATE OF current_stage_id ON applications
FOR EACH ROW EXECUTE FUNCTION log_stage_change();