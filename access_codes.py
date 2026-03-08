from __future__ import annotations

import random
from datetime import datetime, timezone
from dataclasses import dataclass

# Characters chosen to stay readable in print/scans:
# - no 0/O
# - no 1/I/L
# - no 5/S confusion by excluding 5
# - no 2/Z confusion if you want stricter readability
PERMISSIBLE_CHARS = list("2346789ABCDEFGHJKMNPQRTUVWXY")
DATETIME_FORMAT = "%Y%m%d-%H%M%S"

@dataclass(slots=True)
class AccessCode:
    id: str
    secret: str
    datetime: datetime
    sheet_id: int
    valid: bool = True

    def invalidate(self) -> None:
        """Mark the code as used."""
        self.valid = False

    def is_valid(self) -> bool:
        """Check if the code can still be used."""
        return self.valid
    
    def __str__(self) -> str:
        """Serialize AccessCode to file format (just the code id)."""
        return self.id
    
    @classmethod
    def from_string(cls, code_str: str) -> AccessCode:
        """Parse a code string into an AccessCode object."""
        validate_code_format(code_str)

        random_part = code_str[0:6]
        date_part = code_str[7:15]
        time_part = code_str[16:22]
        sheet_part = code_str[24:28]

        dt = datetime.strptime(f"{date_part}-{time_part}", "%Y%m%d-%H%M%S")
        sheet_id = int(sheet_part)

        return cls(
            id=code_str,
            secret=random_part,
            datetime=dt,
            sheet_id=sheet_id,
            valid=True,
        )


def validate_access_code(
    id: str,
    secret: str,
    dt: datetime,
    sheet_id: int,
    valid: bool,
) -> None:
    """Validate AccessCode fields."""

    if not isinstance(id, str) or not id:
        raise ValueError("id must be a non-empty string")

    if not isinstance(secret, str) or len(secret) != 6:
        raise ValueError("secret must be a 6-character string")

    for ch in secret:
        if ch not in PERMISSIBLE_CHARS:
            raise ValueError(f"Invalid character in secret: {ch}")

    if not isinstance(dt, datetime):
        raise ValueError("datetime must be a datetime object")

    if not isinstance(sheet_id, int) or not (0 <= sheet_id <= 9999):
        raise ValueError("sheet_id must be an integer in range 0..9999")

    if not isinstance(valid, bool):
        raise ValueError("valid must be a boolean")
    
def generate_code_str(sheet_id: int) -> str:
    """
    Generate a code in the format:
        {6_random}-{readable_timestamp}-{sheet_id_4_digits_0_padded}

    Example:
        7KMQ8A-20260307-154522-S0042

    Format parts:
    - 6_random: random chars from PERMISSIBLE_CHARS
    - readable_timestamp: YYYYMMDD-HHMMSS in UTC
    - sheet_id: 4 digits, zero-padded
    """
    if not 0 <= sheet_id <= 9999:
        raise ValueError("sheet_id must be in range 0..9999")

    rng = random.SystemRandom()

    random_part = "".join(rng.choice(PERMISSIBLE_CHARS) for _ in range(6))
    timestamp_part = datetime.now(timezone.utc).strftime(DATETIME_FORMAT)
    sheet_part = f"{sheet_id:04d}"

    return f"{random_part}-{timestamp_part}-{sheet_part}"


def validate_code_format(code: str) -> None:
    """
    Validate code structure and characters.

    Raises ValueError if invalid.
    """

    if len(code) != 27:
        raise ValueError("Invalid code length")

    if code[6] != "-":
        raise ValueError("Missing '-' at position 6")

    if code[15] != "-":
        raise ValueError("Missing '-' at position 15")

    if code[22] != "-":
        raise ValueError("Missing '-' at position 21")


    random_part = code[0:6]
    date_part = code[7:15]
    time_part = code[16:22]
    sheet_part = code[23:27]

    for ch in random_part:
        if ch not in PERMISSIBLE_CHARS:
            raise ValueError(f"Invalid character in random part: {ch}")

    if not date_part.isdigit():
        raise ValueError("Date part must be digits")

    if not time_part.isdigit():
        raise ValueError("Time part must be digits")

    if not sheet_part.isdigit():
        raise ValueError("Sheet ID must be digits")

    # validate timestamp correctness
    datetime.strptime(f"{date_part}-{time_part}", "%Y%m%d-%H%M%S")


