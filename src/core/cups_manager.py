import cups
import json
import os
import sqlite3
import threading

from .logger import logger
from ..db.models.printerjob import JobStatus


class MarkerCache:
    """
    Lightweight SQLite-backed store for the last known valid marker readings.
    Schema: one row per (printer_name, marker_index) holding the full marker
    dict serialised as JSON.  Index is the 0-based position in the CUPS
    marker arrays, which is stable across polls even if the name changes.
    """

    def __init__(self, db_path: str):
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()  # one connection per thread
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        if not getattr(self._local, "conn", None):
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self):
        self._conn().execute(
            """
            CREATE TABLE IF NOT EXISTS marker_cache_v2 (
                printer_name  TEXT    NOT NULL,
                marker_index  INTEGER NOT NULL,
                data          TEXT    NOT NULL,
                PRIMARY KEY (printer_name, marker_index)
            )
            """
        )
        self._conn().commit()

    def get_all(self, printer_name: str) -> dict[int, dict]:
        """Return {marker_index: marker_dict} for the given printer."""
        rows = self._conn().execute(
            "SELECT marker_index, data FROM marker_cache_v2 WHERE printer_name = ?",
            (printer_name,),
        ).fetchall()
        return {row["marker_index"]: json.loads(row["data"]) for row in rows}

    def set_many(self, printer_name: str, indexed_markers: list[tuple[int, dict]]):
        """Upsert a batch of (index, marker_dict) pairs for the given printer."""
        conn = self._conn()
        conn.executemany(
            """
            INSERT INTO marker_cache_v2 (printer_name, marker_index, data)
            VALUES (?, ?, ?)
            ON CONFLICT (printer_name, marker_index) DO UPDATE SET data = excluded.data
            """,
            [
                (printer_name, idx, json.dumps(m))
                for idx, m in indexed_markers
            ],
        )
        conn.commit()

    def delete_all(self, printer_name: str):
        """Delete all marker cache rows for the given printer."""
        conn = self._conn()
        conn.execute(
            "DELETE FROM marker_cache_v2 WHERE printer_name = ?",
            (printer_name,)
        )
        conn.commit()


class CUPSManager:
    def __init__(self):
        try:
            self.conn = cups.Connection()
        except Exception as e:
            logger.error(f"Failed to connect to CUPS: {e}")
            self.conn = None

        # pycups / libcups is not thread-safe: serialise all calls.
        self._lock = threading.Lock()

        self.CUPS_STATE_MAP = {
            3: "idle",
            4: "printing",
            5: "stopped"
        }

        self.JOB_STATE_MAP = {
            3: JobStatus.PENDING,
            4: JobStatus.HELD,
            5: JobStatus.PRINTING,
            6: JobStatus.STOPPED,
            7: JobStatus.CANCELLED,
            8: JobStatus.ABORTED,
            9: JobStatus.COMPLETED
        }

        self.MAX_TRIES = 3
        self.jobs_with_error = {}

        from .config import settings
        self._marker_cache = MarkerCache(settings.PRINTER_MARKERS_DB)

    def get_printers(self) -> list[dict]:
        """
        Returns CUPS printers info on a list of dictionaries
        """
        if self.conn is None:
            return []

        try:
            with self._lock:
                printers = self.conn.getPrinters()
        except cups.IPPError:
            logger.error("CUPS Error, unable to retrieve printers")
            return []
        
        result = []
        for name, attrs in printers.items():
            raw_reasons = attrs.get("printer-state-reasons", [])
            # "none" is CUPS's default value meaning no issues — discard it
            state_reasons = [r for r in raw_reasons if r != "none"]
            result.append({
                "name": name,
                "location": attrs.get("printer-location"),
                "status": self.CUPS_STATE_MAP.get(attrs.get("printer-state"), "unknown"),
                "state_reasons": state_reasons,
            })
        
        return result

    def print_file(
        self,
        printer_name: str,
        file_path: str,
        title: str,
        options: dict
    ) -> str:
        
        if self.conn is None:
            return ""
        
        try:
            with self._lock:
                job_id = self.conn.printFile(
                    printer=printer_name,
                    filename=file_path,
                    title=title,
                    options=options
                )
            return str(job_id)
        
        except cups.IPPError:
            return ""
        
        except Exception as e:
            print(e)
            return ""
        
    def _merge_with_cache(self, printer_name: str, raw_markers: list[dict]) -> list[dict]:
        """
        Merges a raw marker list with the persistent cache so that:
        - A marker present with level == -1 is replaced with its last known
          valid level from the cache (if one exists).
        - A marker that was previously known but is absent from the current
          CUPS response is re-inserted from the cache.
        The cache itself is updated with every valid (level != -1) reading.
        Markers are matched by their 0-based position (index) so that a name
        change between polls simply overwrites the cached name.
        """
        with self._lock:
            printer_cache = self._marker_cache.get_all(printer_name)  # {index: dict}

            to_persist: list[tuple[int, dict]] = []
            for i, m in enumerate(raw_markers):
                if m["level"] != -1:
                    to_persist.append((i, m))
                elif i not in printer_cache:
                    # No prior reading; register so the marker is known.
                    to_persist.append((i, m))

            if to_persist:
                self._marker_cache.set_many(printer_name, to_persist)
                for idx, m in to_persist:
                    printer_cache[idx] = m

            seen_indices = set(range(len(raw_markers)))

            merged = []
            for i, m in enumerate(raw_markers):
                if m["level"] != -1:
                    merged.append(m)
                else:
                    cached = printer_cache.get(i)
                    merged.append(
                        cached if (cached and cached["level"] != -1) else m
                    )

            # Re-insert markers absent from the current CUPS response.
            for idx, cached_m in printer_cache.items():
                if idx not in seen_indices:
                    merged.append(dict(cached_m))

        return merged

    def get_toner_levels(self, printer_name: str) -> list[dict] | None:
        """
        Returns toner/ink marker levels for the given CUPS printer.
        Returns None if CUPS is unavailable or the printer is not found.
        Returns an empty list if the printer does not report marker info.
        Each entry: {name, color, level, low_level, high_level}
        level == -1 means the driver cannot report a value for that slot.
        """
        if self.conn is None:
            return None

        try:
            with self._lock:
                attrs = self.conn.getPrinterAttributes(printer_name)
        except cups.IPPError:
            return None

        try:
            levels = attrs.get("marker-levels")
            names = attrs.get("marker-names")
            colors = attrs.get("marker-colors")
            low = attrs.get("marker-low-levels")
            high = attrs.get("marker-high-levels")
            types = attrs.get("marker-types")

            if levels is None or names is None:
                return []

            def to_list(v):
                return v if isinstance(v, list) else [v]

            def safe_int(v, default):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return default

            levels = [safe_int(x, -1) for x in to_list(levels)]
            names = [str(x) for x in to_list(names)]
            colors = (
                [str(x) if x is not None else None for x in to_list(colors)]
                if colors is not None
                else [None] * len(names)
            )
            low = (
                [safe_int(x, 10) for x in to_list(low)]
                if low is not None
                else [10] * len(names)
            )
            high = (
                [safe_int(x, 100) for x in to_list(high)]
                if high is not None
                else [100] * len(names)
            )
            types = (
                [str(x) if x is not None else None for x in to_list(types)]
                if types is not None
                else [None] * len(names)
            )

            n = len(names)
            if n == 0:
                return []

            raw_markers = [
                {
                    "name": names[i],
                    "color": colors[i] if i < len(colors) else None,
                    "level": levels[i] if i < len(levels) else -1,
                    "low_level": low[i] if i < len(low) else 10,
                    "high_level": high[i] if i < len(high) else 100,
                    "marker_type": types[i] if i < len(types) else None,
                }
                for i in range(n)
            ]

            return self._merge_with_cache(printer_name, raw_markers)
        except Exception:
            logger.error(f"Unexpected error parsing toner levels for {printer_name}")
            return []

    def get_job_status(self, cups_id: int) -> JobStatus | None:
        if self.conn is None:
            return None

        try:
            with self._lock:
                attrs = self.conn.getJobAttributes(cups_id)
        except cups.IPPError as e:
            logger.warning(f"Failed to get CUPS job attributes for job {cups_id}: {e}")

            if cups_id not in self.jobs_with_error:
                self.jobs_with_error[cups_id] = 0
            self.jobs_with_error[cups_id] += 1

            if self.jobs_with_error[cups_id] > self.MAX_TRIES:
                self.jobs_with_error.pop(cups_id)
                return JobStatus.ABORTED
            
            return None

        cups_state = attrs["job-state"]

        return self.JOB_STATE_MAP[cups_state]


# Single shared instance — every caller in the app talks to the same CUPS
# connection, lock, and error-retry/marker-cache state instead of each
# maintaining its own.
cups_manager = CUPSManager()
