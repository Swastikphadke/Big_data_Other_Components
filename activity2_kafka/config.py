"""Activity 2 - shared configuration (broker, topics, detection thresholds)."""

BOOTSTRAP_SERVERS = "localhost:9092"

TOPIC_READINGS = "traffic-readings"     # sensor events, keyed by junction_id
TOPIC_ALERTS = "congestion-alerts"      # alerts emitted by the detector
READINGS_PARTITIONS = 3

# ------------------------------------------------------------------ detection
# All thresholds are applied to a ROLLING AVERAGE of the last WINDOW readings of
# the same junction (one reading = one simulated minute), never to one reading,
# so a single faulty sample cannot raise an alert.
WINDOW = 5

CONGESTION_SPEED_KMPH = 20.0   # avg speed below this ...
CONGESTION_MIN_COUNT = 45.0    # ... AND avg vehicles/min at or above this -> CONGESTION
INCIDENT_SPEED_KMPH = 15.0     # avg speed below this ...
INCIDENT_MAX_COUNT = 30.0      # ... AND avg vehicles/min below this -> INCIDENT (blockage)
CLEAR_SPEED_KMPH = 25.0        # alert clears only when avg speed recovers above this (hysteresis)


def severity(avg_speed):
    """Severity band of an open alert, from rolling average speed."""
    if avg_speed < 10:
        return "SEVERE"
    if avg_speed < 15:
        return "HEAVY"
    return "MODERATE"
