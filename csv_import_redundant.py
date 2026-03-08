from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, Optional
from access_codes import AccessCode

# -------- In-memory store --------
# O(1) average lookup by code, which is what you want later for fast validation.
class CodeStore:
    def __init__(self) -> None:
        self._by_code: Dict[str, AccessCode] = {}

    def add(self, record: AccessCode) -> None:
        if record.id in self._by_code:
            raise ValueError(f"Duplicate code detected: {record.id}")
        self._by_code[record.id] = record

    def get(self, code: str) -> Optional[AccessCode]:
        return self._by_code.get(code)

    def is_valid(self, code: str) -> bool:
        record = self._by_code.get(code)
        return record is not None and record.valid

    def invalidate(self, code: str) -> bool:
        record = self._by_code.get(code)
        if record is None or not record.valid:
            return False
        record.valid = False
        return True

    def __len__(self) -> int:
        return len(self._by_code)


# -------- CSV loading --------

def load_codes_from_csv(csv_path: Path) -> CodeStore:
    store = CodeStore()

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_columns = {"id", "sheet_id", "secret", "datetime"}
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or missing a header row.")

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            try:
                record = AccessCode.from_string(row["id"])

                if not record.id:
                    raise ValueError("Code cannot be empty.")

                store.add(record)

            except Exception as exc:
                raise ValueError(
                    f"Error in {csv_path.name} at line {line_number}: {exc}"
                ) from exc

    return store


def mark_file_as_consumed(csv_path: Path) -> Path:
    # Example:
    # codes.csv -> codes.consumed.csv
    consumed_path = csv_path.with_name(f"{csv_path.stem}.consumed{csv_path.suffix}")

    if consumed_path.exists():
        raise FileExistsError(
            f"Cannot mark CSV as consumed because target already exists: {consumed_path}"
        )

    csv_path.rename(consumed_path)
    return consumed_path


# -------- Main --------
def main() -> int:
    script_dir = Path(__file__).resolve().parent
    csv_path = script_dir / "codes.csv"

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return 1

    try:
        store = load_codes_from_csv(csv_path)
        consumed_path = mark_file_as_consumed(csv_path)

        print(f"Loaded {len(store)} codes into memory.")
        print(f"Marked source file as consumed: {consumed_path.name}")

        # Demo lookups
        print("\nInteractive test mode. Enter a code to check it.")
        print("Press Ctrl+C or Ctrl+D to exit.\n")

        while True:
            user_code = input("Code> ").strip()
            if not user_code:
                continue

            if store.is_valid(user_code):
                print("VALID")
                # For single-use codes, invalidate immediately after successful use:
                store.invalidate(user_code)
                print("Code has now been marked as used/invalid in memory.")
            else:
                print("INVALID")

    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except Exception as exc:
        print(f"Startup error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())