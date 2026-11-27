-- 04_queries.sql
-- Example queries on the recruitment schema.
-- The data is synthetic, so the results only show that the queries work.

-- 1. Funnel: how many applications reached each stage
WITH reached AS (
    SELECT s.stage_id, s.name, s.sort_order,
           COUNT(DISTINCT h.application_id) AS apps
    FROM stages s
    LEFT JOIN application_stage_history h ON h.to_stage_id = s.stage_id
    WHERE s.stage_id <> 6                      -- leave out Rejected
    GROUP BY s.stage_id, s.name, s.sort_order
)
SELECT name, apps,
       ROUND(100.0 * apps / FIRST_VALUE(apps) OVER (ORDER BY sort_order), 1) AS pct_of_applied
FROM reached
ORDER BY sort_order;

-- 2. Average days spent in each stage (uses the history table)
WITH durations AS (
    SELECT to_stage_id AS stage_id,
           LEAD(changed_at) OVER (PARTITION BY application_id ORDER BY changed_at)
               - changed_at AS time_in_stage
    FROM application_stage_history
)
SELECT s.name,
       ROUND(AVG(EXTRACT(EPOCH FROM d.time_in_stage)) / 86400, 1) AS avg_days
FROM durations d
JOIN stages s USING (stage_id)
WHERE d.time_in_stage IS NOT NULL
GROUP BY s.stage_id, s.name, s.sort_order
ORDER BY s.sort_order;

-- 3. Hire rate by source
SELECT source,
       COUNT(*) AS applications,
       COUNT(*) FILTER (WHERE current_stage_id = 5) AS hired,
       ROUND(100.0 * COUNT(*) FILTER (WHERE current_stage_id = 5) / COUNT(*), 1) AS hire_rate_pct
FROM applications
GROUP BY source
ORDER BY hire_rate_pct DESC;