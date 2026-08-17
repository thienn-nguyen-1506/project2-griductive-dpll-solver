"""Pure GUI copy checks for rejected verdict feedback."""

import unittest

from gui.models import (
    ActionCode,
    CellView,
    Status,
    build_verdict_feedback,
)


class TestVerdictFeedback(unittest.TestCase):
    def setUp(self) -> None:
        self.cell = CellView(cell_id="B2", name="Bella", profession="Guard")

    def test_not_provable_and_contradicted_are_visibly_distinct(self) -> None:
        not_provable = build_verdict_feedback(
            ActionCode.NOT_PROVABLE,
            self.cell,
            Status.CRIMINAL,
        )
        contradicted = build_verdict_feedback(
            ActionCode.CONTRADICTED,
            self.cell,
            Status.CRIMINAL,
        )

        self.assertEqual(not_provable.title, "Not Provable Yet")
        self.assertIn("both possibilities", not_provable.main)
        self.assertEqual(contradicted.title, "Verdict Contradicted")
        self.assertIn("Bella is Innocent", contradicted.main)
        self.assertNotEqual(not_provable.icon, contradicted.icon)
        self.assertNotEqual(not_provable.tone, contradicted.tone)


if __name__ == "__main__":
    unittest.main()
