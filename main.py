from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from pathlib import Path

from access_codes import AccessCode, validate_code_format
from code_file_io import load_codes_from_file
from db import create_connection
from db import (
    create_table,
    get_code_by_id,
    upsert_code,
    invalidate_code,
)
from polling import get_scan

# Assumed to already exist elsewhere in your project.
# Adjust the module name if needed.
from hardware_control import red_led, run_device


LOG = logging.getLogger("main_controller")

DB_PATH = Path(__file__).resolve().parent / "access_codes.db"
WATCH_DIR = Path(__file__).resolve().parent
CSV_GLOB = "*.csv"
TXT_GLOB = "*.txt"
CONSUMED_SUFFIX = ".consumed"
POLL_INTERVAL_SEC = 0.1


def mark_file_consumed(file_path: Path) -> Path:
    datetime_str = "." + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    consumed_path = file_path.with_name(
        f"{file_path.stem}{datetime_str}{CONSUMED_SUFFIX}{file_path.suffix}"
    )

    if consumed_path.exists():
        raise FileExistsError(f"Consumed file already exists: {consumed_path.name}")

    file_path.rename(consumed_path)
    return consumed_path


class MainController:
    def __init__(self, db_path: Path, watch_dir: Path) -> None:
        self.db_path = db_path
        self.watch_dir = watch_dir
        self.conn = None

    def open_database(self) -> None:
        self.conn = create_connection(self.db_path)
        create_table(self.conn)
        self.conn.commit()
        LOG.info("Database opened: %s", self.db_path)

    def close_database(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            LOG.info("Database closed")

    def iter_pending_csv_files(self) -> list[Path]:
        files = sorted(self.watch_dir.glob(CSV_GLOB))
        return [p for p in files if not p.stem.endswith(CONSUMED_SUFFIX)]

    def iter_pending_txt_files(self) -> list[Path]:
        files = sorted(self.watch_dir.glob(TXT_GLOB))
        return [p for p in files if not p.stem.endswith(CONSUMED_SUFFIX)]
    
    def import_file(self, file_path: Path) -> None:
        LOG.info("Importing codes from %s", file_path.name)

        codes: dict[str, AccessCode] = load_codes_from_file(file_path)
        duplicates = 0
        inserted = 0

        # Batch inside a transaction for performance
        with self.conn:
            for code_id, code in codes.items():
                existing = get_code_by_id(self.conn, code_id)
                if existing is not None:
                    duplicates += 1
                    LOG.warning("Code already exists, skipping insert: %s", code_id)
                    continue

                upsert_code(self.conn, code)
                inserted += 1
        self.conn.commit()
        consumed_path = mark_file_consumed(file_path)
        LOG.info(
            "Import finished: inserted=%d duplicates=%d marked=%s",
            inserted,
            duplicates,
            consumed_path.name,
        )

    def import_pending_files(self) -> None:
        # no CSV yet, but we can import .txt files with the same format for now
        for file_path in self.iter_pending_txt_files():
            try:
                self.import_file(file_path)
            except Exception:
                LOG.exception("Failed to import file: %s", file_path.name)

    def handle_scan(self, scanned_code: str) -> None:
        scanned_code = scanned_code.strip()
        if not scanned_code:
            return

        LOG.info("Scan received: %s", scanned_code)

        try:
            validate_code_format(scanned_code)
        except Exception:
            LOG.warning("Rejected scan with invalid format: %s", scanned_code)
            red_led()
            return

        code = get_code_by_id(self.conn, scanned_code)
        if code is None:
            LOG.warning("Rejected scan: code not found after validation: %s", scanned_code)
            red_led()
            return

        if not code.valid:
            LOG.warning("Rejected scan: code invalid: %s", scanned_code)
            red_led()
            return

        LOG.info("Accepted scan: %s", scanned_code)

        try:
            run_device()
        except Exception:
            LOG.exception("run_device failed for code: %s", scanned_code)
            red_led()
            return

        code.invalidate()

        if not invalidate_code(self.conn, scanned_code):
            LOG.warning("Code was accepted but DB invalidation failed: %s", scanned_code)
            return

        # Persist invalidation
        self.conn.commit()

        LOG.info("Code invalidated after successful device run: %s", scanned_code)

    def poll_scan_once(self) -> None:
        try:
            scanned_code = get_scan()
        except Exception:
            LOG.exception("Polling failed")
            return

        if scanned_code:
            self.handle_scan(scanned_code)

    def run(self) -> None:
        self.open_database()

        try:
            while True:
                self.import_pending_files()
                self.poll_scan_once()
                time.sleep(POLL_INTERVAL_SEC)
        finally:
            self.close_database()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    controller = MainController(
        db_path=DB_PATH,
        watch_dir=WATCH_DIR,
    )
    controller.run()


if __name__ == "__main__":
    main()