"""Enforce repository-owned Python source formatting constraints."""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
FORMAL_PYTHON_ROOTS = (
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "tests",
    PROJECT_ROOT / "eval",
)
MAX_LINE_LENGTH = 80


class PythonLineLengthTests(unittest.TestCase):
    def test_formal_python_lines_do_not_exceed_eighty_characters(self) -> None:
        violations: list[str] = []
        for root in FORMAL_PYTHON_ROOTS:
            for path in sorted(root.rglob("*.py")):
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(),
                    start=1,
                ):
                    if len(line) > MAX_LINE_LENGTH:
                        relative_path = path.relative_to(PROJECT_ROOT)
                        violations.append(
                            f"{relative_path}:{line_number}: {len(line)}"
                        )

        self.assertEqual(
            violations,
            [],
            "Python lines exceed 80 characters:\n" + "\n".join(violations),
        )

    def test_eval_json_lines_do_not_exceed_eighty_characters(self) -> None:
        violations: list[str] = []
        for path in sorted((PROJECT_ROOT / "eval").rglob("*.json")):
            for line_number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if len(line) > MAX_LINE_LENGTH:
                    relative_path = path.relative_to(PROJECT_ROOT)
                    violations.append(
                        f"{relative_path}:{line_number}: {len(line)}"
                    )

        self.assertEqual(
            violations,
            [],
            "Eval JSON lines exceed 80 characters:\n"
            + "\n".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
