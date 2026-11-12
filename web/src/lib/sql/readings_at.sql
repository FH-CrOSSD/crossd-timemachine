-- Hindsight guard: the latest reading per component that was read at or before t0.
-- `observed` is when the value was read from its source; the snapshot date plays no part.
-- Parameters: 1 project, 2 t0 (epoch seconds, UTC).
SELECT project, instrument, component, value, note, observed, snapshot, evidence, source
FROM (
  SELECT *, row_number() OVER (PARTITION BY instrument, component ORDER BY observed DESC) AS rn
  FROM readings
  WHERE project = ? AND observed <= ?
)
WHERE rn = 1
ORDER BY instrument, component
