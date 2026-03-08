from pathlib import Path
from pathlib import Path
from typing import Iterable

from access_codes import AccessCode


def load_codes_from_file(file_path: Path) -> dict[str, AccessCode]:
    """
    Reads a file containing comma-separated codes and loads them into memory.

    Example format:
        CODE1,CODE2,CODE3
        CODE4,CODE5
    """

    codes: dict[str, AccessCode] = {}

    with file_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):

            line = line.strip()
            if not line:
                continue

            parts = [p.strip() for p in line.split(",") if p.strip()]

            for code_str in parts:
                parsed = AccessCode.from_string(code_str)

                code = AccessCode(
                    id=code_str,
                    secret=parsed.secret,
                    datetime=parsed.datetime,
                    sheet_id=parsed.sheet_id,
                )

                if code.id in codes:
                    raise ValueError(f"Duplicate code at line {line_number}: {code.id}")

                codes[code.id] = code

    return codes




def save_codes_to_file(path: Path, codes: Iterable[AccessCode]) -> None:
    """
    Save AccessCode objects to a comma-separated file.
    """

    with path.open("w", encoding="utf-8") as f:
        first = True

        for code in codes:
            if not first:
                f.write(",")
            f.write(str(code))
            first = False
            
if __name__ == "__main__":
    path = Path.cwd() / f"codes.txt"
    codes = load_codes_from_file(path)
    print(f"Loaded {len(codes)} codes from {path}:")
    for code in codes.values():
        print(f"  - {code.id}")