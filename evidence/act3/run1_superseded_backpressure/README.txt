RUN 1 - SUPERSEDED (kept for transparency / viva discussion)
Job 7308cce1f85b5c92ad86b8374045b4af, 2026-11-03 19:56-20:06 IST.
Problem found: the EPISODE_RESOLVED MATCH_RECOGNIZE pattern (S X* L) started a new partial
match at every high-score row. During P06's ~58-minute fever (~690 consecutive rows) the number
of live partial matches grew with every row, so per-row work grew quadratically. The Match[16]
operator reached busy=100 %, upstream OverAggregate showed backpressure=high, watermarks stalled
(~11:24-11:42 event time), and the P06 fever-resolution event had not been emitted 4 min after
the producer finished (11 of 12 episode events).
Fix: anchor the pattern at the calm state -> PATTERN (L M* S X* R); see activity3_flink/README.md.
Outputs of run 1 are NOT used as results.
