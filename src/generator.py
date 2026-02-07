import logging
import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("generator")

@dataclass(frozen=True)
class PersonRow:
    person_id: int
    first_name: str
    last_name: str
    email: str
    age: int
    created_at: str  # ISO string

FIRST_NAMES = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Morgan", "Riley"]
LAST_NAMES = ["Smith", "Nguyen", "Khan", "Brown", "Garcia", "Wilson", "Chen"]

def _random_email(first: str, last: str, rng: random.Random) -> str:
    domain = rng.choice(["example.com", "mail.test", "demo.local"])
    suffix = "".join(rng.choices(string.ascii_lowercase + string.digits, k=3))
    return f"{first.lower()}.{last.lower()}.{suffix}@{domain}"

def generate_people(n: int, seed: int = 0) -> list[PersonRow]:
    if n <= 0:
        raise ValueError("n must be > 0")

    rng = random.Random(seed)
    # Deterministic "base_time" so repeatable generation works for tests.
    # Use a fixed epoch in UTC plus a seed-based offset.
    base_time = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=rng.randint(0, 10_000_000))


    rows: list[PersonRow] = []
    for i in range(1, n + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        age = rng.randint(18, 80)
        created_at_dt = base_time - timedelta(seconds=rng.randint(0, 3600))
        created_at = created_at_dt.isoformat().replace("+00:00", "Z")


        row = PersonRow(
            person_id=i,
            first_name=first,
            last_name=last,
            email=_random_email(first, last, rng),
            age=age,
            created_at=created_at,
        )
        rows.append(row)

    logger.info("Generated %d people rows (seed=%d).", n, seed)
    return rows
