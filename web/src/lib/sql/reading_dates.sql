-- Dates only, never values: where the scrubber can stop, and which instrument read on that date.
-- Parameters: 1 project.
SELECT DISTINCT instrument, observed
FROM readings
WHERE project = ?
ORDER BY observed
