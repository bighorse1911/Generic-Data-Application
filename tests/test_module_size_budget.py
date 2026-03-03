from __future__ import annotations

from pathlib import Path
import unittest
import warnings


HARD_LIMIT = 1200
SOFT_LIMIT = 700

HARD_EXEMPTIONS = set()

SOFT_EXEMPTIONS = set(HARD_EXEMPTIONS)


class ModuleSizeBudgetTests(unittest.TestCase):
    def test_module_size_budgets(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        src_root = repo_root / "src"
        failures: list[str] = []
        soft_hits: list[str] = []

        for path in sorted(src_root.rglob("*.py")):
            rel = path.relative_to(repo_root).as_posix()
            line_count = len(path.read_text(encoding="utf-8").splitlines())

            if line_count > HARD_LIMIT and rel not in HARD_EXEMPTIONS:
                failures.append(f"{rel} ({line_count} lines)")
            if line_count > SOFT_LIMIT and rel not in SOFT_EXEMPTIONS:
                soft_hits.append(f"{rel} ({line_count} lines)")

        if soft_hits:
            warnings.warn(
                "Soft module-size budget exceeded (warn-only):\n- " + "\n- ".join(soft_hits),
                stacklevel=1,
            )

        self.assertFalse(
            failures,
            "Hard module-size budget exceeded (>1200 lines):\n- " + "\n- ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()
