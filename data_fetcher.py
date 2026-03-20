"""
DataFetcher — QThread that polls SL APIs and updates BusModel.

APIs used:
  - SL Transport API (no key) — departures, polled every 30s
  - SL Deviations API (no key, max 1/min) — alerts, polled every 60s
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

_STOCKHOLM = ZoneInfo("Europe/Stockholm")

from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt

import config
from bus_model import BusModel, BusRow, ConnectionStatus

log = logging.getLogger(__name__)

# ── API endpoints ─────────────────────────────────────────────────────────

SL_DEPARTURES_URL = (
    "https://transport.integration.sl.se/v1/sites/{site_id}/departures"
)
SL_DEVIATIONS_URL = (
    "https://deviations.integration.sl.se/v1/messages?site={site_id}"
)


# ── Helper: HTTP GET → parsed JSON ────────────────────────────────────────

def _get_json(url: str, timeout: int = 10) -> dict | list | None:
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        log.warning("HTTP %s for %s", e.code, url)
    except URLError as e:
        log.warning("URL error for %s: %s", url, e.reason)
    except Exception as e:
        log.warning("Error fetching %s: %s", url, e)
    return None


# ── Time helpers ──────────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # SL API returns naive local Stockholm time — attach timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_STOCKHOLM)
        return dt
    except ValueError:
        return None


def _hhmm(dt: datetime | None) -> str:
    if dt is None:
        return "--:--"
    return dt.astimezone().strftime("%H:%M")


def _delay_minutes(scheduled: datetime | None, expected: datetime | None) -> int:
    if scheduled is None or expected is None:
        return 0
    return max(0, int((expected - scheduled).total_seconds() / 60))


def _minutes_from_now(dt: datetime | None) -> int:
    if dt is None:
        return 999
    now = datetime.now(timezone.utc)
    return max(0, int((dt - now).total_seconds() / 60))


# ── Which train station does this bus serve? ──────────────────────────────

def _train_site_for_bus(destination: str) -> int | None:
    """Return the SL site ID of the train station matching the bus destination."""
    dest_lower = destination.lower()
    for keyword, site_id in config.TRAIN_STOPS.items():
        if keyword in dest_lower:
            return site_id
    return None


# ── Connection logic ──────────────────────────────────────────────────────

def _find_train_connection(
    bus_expected_dt: datetime,
    trains: list[dict],
) -> tuple[dict | None, ConnectionStatus, int]:
    """
    Find the first southbound pendeltåg this bus can connect to.
    Returns (train_dict, status, change_minutes).
    change_minutes = minutes spare at station before train departs.
    """
    arrival_at_station = bus_expected_dt + timedelta(minutes=config.BUS_TRAVEL_MINUTES)

    for train in trains:
        t_exp = _parse_dt(train.get("expected") or train.get("scheduled"))
        if t_exp is None:
            continue
        margin = (t_exp - arrival_at_station).total_seconds() / 60
        if margin >= config.TRAIN_BUFFER_MINUTES:
            return train, ConnectionStatus.SAFE, int(margin)
        if margin >= 0:
            return train, ConnectionStatus.TIGHT, int(margin)
    return None, ConnectionStatus.MISS, 0


# ── Main thread ───────────────────────────────────────────────────────────

class DataFetcher(QThread):
    alertChanged = pyqtSignal(str)
    statusChanged = pyqtSignal(str)
    rowsReady = pyqtSignal(object)   # emitted with list[BusRow]; picked up on GUI thread

    def __init__(self, model: BusModel, parent=None):
        super().__init__(parent)
        self._model = model
        # Wire rowsReady → model.update via queued connection (crosses thread boundary)
        self.rowsReady.connect(model.update, Qt.ConnectionType.QueuedConnection)
        # Cache: train site_id → list of southbound departures
        self._train_cache: dict[int, list[dict]] = {}

    def run(self):
        log.info("DataFetcher thread started — bus stop %s", config.BUS_STOP_SITE_ID)

        # Initial fetch
        self._fetch_all()

        departures_timer = QTimer()
        departures_timer.setInterval(config.DEPARTURES_POLL_INTERVAL * 1000)
        departures_timer.timeout.connect(self._fetch_all)
        departures_timer.start()

        deviations_timer = QTimer()
        deviations_timer.setInterval(config.DEVIATIONS_POLL_INTERVAL * 1000)
        deviations_timer.timeout.connect(self._fetch_deviations)
        deviations_timer.start()

        self.exec()

    # ── Departures ─────────────────────────────────────────────────────

    def _fetch_all(self):
        # Fetch bus stop
        bus_data = _get_json(SL_DEPARTURES_URL.format(site_id=config.BUS_STOP_SITE_ID))

        # Fetch all relevant train stations
        all_train_site_ids = list(config.TRAIN_STOPS.values())
        self._train_cache = {}
        for site_id in all_train_site_ids:
            train_data = _get_json(SL_DEPARTURES_URL.format(site_id=site_id))
            if train_data:
                self._train_cache[site_id] = self._extract_trains(train_data)

        if bus_data is None:
            self.statusChanged.emit("No data")
            self._model.update([])
            return

        rows = self._build_rows(bus_data)
        log.info("Built %d rows", len(rows))
        for r in rows:
            log.info("  %s → %s in %dmin | train %s delay=%d change=%dmin status=%s",
                     r.line, r.destination, r.minutes,
                     r.train_expected, r.train_delay_minutes, r.change_minutes, r.status.name)
        self.statusChanged.emit("OK")
        self.rowsReady.emit(rows)

    def _build_rows(self, bus_data: dict) -> list[BusRow]:
        now = datetime.now(timezone.utc)
        buses = self._extract_buses(bus_data, now)
        rows: list[BusRow] = []

        for bus_dep in buses[:8]:
            b_sched = _parse_dt(bus_dep.get("scheduled"))
            b_exp = _parse_dt(bus_dep.get("expected") or bus_dep.get("scheduled"))
            if b_exp is None:
                continue

            dest = bus_dep.get("destination", "")
            train_site_id = _train_site_for_bus(dest)
            trains = self._train_cache.get(train_site_id, []) if train_site_id else []

            paired_train, status, change_mins = _find_train_connection(b_exp, trains)

            line_info = bus_dep.get("line", {})
            row = BusRow(
                line=line_info.get("designation", bus_dep.get("line_number", "?")),
                destination=dest,
                minutes=_minutes_from_now(b_exp),
                bus_scheduled=_hhmm(b_sched),
                bus_expected=_hhmm(b_exp),
                bus_delay_minutes=_delay_minutes(b_sched, b_exp),
                status=status if trains else ConnectionStatus.UNKNOWN,
                change_minutes=change_mins,
            )

            if paired_train:
                t_sched = _parse_dt(paired_train.get("scheduled"))
                t_exp = _parse_dt(paired_train.get("expected") or paired_train.get("scheduled"))
                t_line = paired_train.get("line", {})
                row.train_line = t_line.get("designation", "")
                row.train_destination = paired_train.get("destination", "")
                row.train_scheduled = _hhmm(t_sched)
                row.train_expected = _hhmm(t_exp)
                row.train_delay_minutes = _delay_minutes(t_sched, t_exp)

                # Compute arrival at Stockholm C
                train_station_key = next(
                    (k for k, v in config.TRAIN_STOPS.items() if v == train_site_id), None
                )
                travel = config.TRAIN_TO_DESTINATION_MINUTES.get(train_station_key, 22)
                if t_exp:
                    arrive_dt = t_exp + timedelta(minutes=travel)
                    row.arrive_time = _hhmm(arrive_dt)
                    row.arrive_minutes = _minutes_from_now(arrive_dt)

            rows.append(row)

        return rows

    def _extract_buses(self, data: dict, now: datetime) -> list[dict]:
        deps = data.get("departures", [])
        result = []
        for dep in deps:
            line = dep.get("line", {})
            mode = line.get("transport_mode", dep.get("transport_mode", ""))
            if mode and "BUS" not in str(mode).upper():
                continue
            # Only buses going to a station we know about
            dest = dep.get("destination", "")
            if not _train_site_for_bus(dest):
                continue
            exp = _parse_dt(dep.get("expected") or dep.get("scheduled"))
            if exp and exp >= now - timedelta(seconds=30):
                result.append(dep)
        result.sort(key=lambda d: _parse_dt(d.get("expected") or d.get("scheduled")) or now)
        return result

    def _extract_trains(self, data: dict) -> list[dict]:
        """Return upcoming southbound pendeltåg sorted by expected time."""
        now = datetime.now(timezone.utc)
        deps = data.get("departures", [])
        result = []
        for dep in deps:
            line = dep.get("line", {})
            # Must be a train
            if line.get("transport_mode", "") != "TRAIN":
                continue
            # Must be heading toward Stockholm (southbound)
            dest = dep.get("destination", "")
            if not any(kw.lower() in dest.lower() for kw in config.TRAIN_TOWARD_STOCKHOLM):
                continue
            exp = _parse_dt(dep.get("expected") or dep.get("scheduled"))
            if exp and exp >= now - timedelta(seconds=30):
                result.append(dep)
        result.sort(key=lambda d: _parse_dt(d.get("expected") or d.get("scheduled")) or now)
        return result[:config.MAX_TRAINS_TO_SCAN]

    # ── Deviations ──────────────────────────────────────────────────────

    def _fetch_deviations(self):
        alerts = []
        site_ids = [config.BUS_STOP_SITE_ID] + list(config.TRAIN_STOPS.values())
        for site_id in site_ids:
            data = _get_json(SL_DEVIATIONS_URL.format(site_id=site_id))
            if data:
                messages = data if isinstance(data, list) else data.get("deviations", [])
                for msg in messages:
                    text = msg.get("header") or msg.get("message", "")
                    if text and text not in alerts:
                        alerts.append(text)
        self.alertChanged.emit("  •  ".join(alerts[:3]) if alerts else "")
