"""
BusTimer configuration — all values read from environment variables.
See bustimer.env for the full list of variables to set.
"""

import os


def _int(key, default):
    return int(os.environ.get(key, default))

def _str(key, default=""):
    return os.environ.get(key, default)


# Trafiklab API key — used for stop ID lookup only
TRAFIKLAB_API_KEY = _str("TRAFIKLAB_API_KEY")

# Timing (minutes)
WALK_TO_STOP_MINUTES  = _int("WALK_TO_STOP_MINUTES", 5)
BUS_TRAVEL_MINUTES    = _int("BUS_TRAVEL_MINUTES", 8)
TRAIN_BUFFER_MINUTES  = _int("TRAIN_BUFFER_MINUTES", 2)

# SL Transport API site IDs
BUS_STOP_SITE_ID = _int("BUS_STOP_SITE_ID", 5838)   # Slåttervägen

TRAIN_STOPS = {
    "jakobsberg": _int("TRAIN_STOP_JAKOBSBERG", 9702),
    "barkarby":   _int("TRAIN_STOP_BARKARBY",   9703),
}

# Destinations meaning "toward Stockholm C" (southbound)
TRAIN_TOWARD_STOCKHOLM = [
    "Nynäshamn", "Västerhaninge", "Södertälje", "Gnesta", "Stockholms",
]

# Travel time train station → Stockholm C
TRAIN_TO_DESTINATION_MINUTES = {
    "jakobsberg": _int("TRAIN_TRAVEL_JAKOBSBERG", 22),
    "barkarby":   _int("TRAIN_TRAVEL_BARKARBY",   18),
}
DESTINATION_NAME = _str("DESTINATION_NAME", "Stockholm C")

# Poll intervals (seconds)
DEPARTURES_POLL_INTERVAL = _int("DEPARTURES_POLL_INTERVAL", 30)
DEVIATIONS_POLL_INTERVAL = _int("DEVIATIONS_POLL_INTERVAL", 60)

MAX_TRAINS_TO_SCAN = _int("MAX_TRAINS_TO_SCAN", 6)
