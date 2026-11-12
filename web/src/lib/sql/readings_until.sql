-- Hindsight guard: every reading of one component read at or before t0, for the timeline.
-- Parameters: 1 project, 2 instrument, 3 component, 4 t0 (epoch seconds, UTC).
SELECT observed, value, note, evidence
FROM readings
WHERE project = ? AND instrument = ? AND component = ? AND observed <= ?
ORDER BY observed
