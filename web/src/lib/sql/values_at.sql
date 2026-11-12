-- The latest reading of one component for every project, read at or before t0. Look-alikes only.
SELECT project, value, observed
FROM (SELECT project, value, observed,
             row_number() OVER (PARTITION BY project ORDER BY observed DESC) AS rn
      FROM readings WHERE instrument = ? AND component = ? AND observed <= ?)
WHERE rn = 1
