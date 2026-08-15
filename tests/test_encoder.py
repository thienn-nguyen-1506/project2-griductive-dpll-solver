"""
tests/test_encoder.py
Unit tests nâng cao cho CNFEncoder, Clue Evaluator, Region Helper
và đóng gói KnowledgeBaseSnapshot.
"""

import unittest
from core.encoder import Clue, ClueEvaluator, CNFEncoder, RegionHelper
from core.dpll import DPLLSolver


class TestCNFEncoder(unittest.TestCase):
    """Unit tests cho CNFEncoder, Clue model, và đóng gói KnowledgeBaseSnapshot."""

    def setUp(self) -> None:
        """Khởi tạo Encoder với danh sách ô mẫu trước mỗi testcase."""
        self.cell_ids = ["A1", "A2", "A3", "B1", "B2", "B3"]
        self.encoder = CNFEncoder(character_ids=self.cell_ids)

    # ------------------------------------------------------------
    # 1. Tests cho RegionHelper & Clue Initialization
    # ------------------------------------------------------------

    def test_region_helper(self) -> None:
        """Kiểm tra các hàm hỗ trợ sinh vùng tọa độ và ô lân cận."""
        row = RegionHelper.get_row(3, 1)
        self.assertEqual(row, ["A1", "B1", "C1"])

        col = RegionHelper.get_column(3, "A")
        self.assertEqual(col, ["A1", "A2", "A3"])

        # Lân cận 8 hướng (kể cả đường chéo)
        neighbors_diag = RegionHelper.get_neighbors(
            3, "B2", include_diagonals=True
        )
        self.assertEqual(len(neighbors_diag), 8)

        # Lân cận 4 hướng (chỉ trực giao)
        neighbors_ortho = RegionHelper.get_neighbors(
            3, "B2", include_diagonals=False
        )
        self.assertEqual(len(neighbors_ortho), 4)

    def test_clue_post_init_and_legacy_support(self) -> None:
        """Kiểm tra tính tương thích ngược và tự động khởi tạo thuộc tính của Clue."""
        clue = Clue(clue_type="EXACTLY", region=["A1", "A2"], k=1)
        self.assertEqual(clue.type, "EXACTLY")
        self.assertEqual(clue.target_cells, ["A1", "A2"])
        self.assertEqual(clue.value, 1)
        self.assertTrue(clue.id.startswith("clue_EXACTLY_"))

        # Kiểm tra trường hợp truyền đơn char_a
        clue_single = Clue(type="FACT", char_a="A1", is_criminal=True)
        self.assertEqual(clue_single.target_cells, ["A1"])

    # ------------------------------------------------------------
    # 2. Tests cho Variable Mapping & Known Statuses
    # ------------------------------------------------------------

    def test_variable_mapping(self) -> None:
        """Kiểm tra ánh xạ cell_id -> biến SAT dạng số nguyên nguyên tố."""
        v1 = self.encoder._get_or_create_cell_var("A1")
        v2 = self.encoder._get_or_create_cell_var("A2")
        v1_again = self.encoder._get_or_create_cell_var("A1")

        self.assertEqual(v1, 1)
        self.assertEqual(v2, 2)
        self.assertEqual(v1, v1_again)  # Đảm bảo không tạo trùng lặp ID biến

    def test_encode_known_statuses(self) -> None:
        """Kiểm tra mã hóa ô đã biết (CRIMINAL -> [v], INNOCENT -> [-v])."""
        known = {"A1": "CRIMINAL", "A2": "INNOCENT"}
        clauses = self.encoder.encode_known_statuses(known)

        v_a1 = self.encoder._get_or_create_cell_var("A1")
        v_a2 = self.encoder._get_or_create_cell_var("A2")

        self.assertIn([v_a1], clauses)
        self.assertIn([-v_a2], clauses)

    # ------------------------------------------------------------
    # 3. Tests cho Mã hóa Clue thành CNF (CNF Encoding)
    # ------------------------------------------------------------

    def test_encode_fact_and_implies(self) -> None:
        """Kiểm tra mã hóa FACT và IMPLIES."""
        v_a1 = self.encoder._get_or_create_cell_var("A1")
        v_a2 = self.encoder._get_or_create_cell_var("A2")

        # FACT
        c_fact = Clue(type="FACT", target_cells=["A1"], value="INNOCENT")
        clauses_fact = self.encoder.encode_clue(c_fact)
        self.assertEqual(clauses_fact, [[-v_a1]])

        # IMPLIES (A1 -> A2 <=> NOT A1 OR A2)
        c_imp = Clue(type="IMPLIES", target_cells=["A1", "A2"])
        clauses_imp = self.encoder.encode_clue(c_imp)
        self.assertEqual(clauses_imp, [[-v_a1, v_a2]])

    def test_encode_exact_count_clue(self) -> None:
        """Kiểm tra mã hóa clue EXACT_COUNT (k=1 cho 2 ô)."""
        clue = Clue(
            id="c1",
            type="EXACT_COUNT",
            target_cells=["A1", "A2"],
            value=1,
        )
        clauses = self.encoder.encode_clue(clue)
        self.assertGreaterEqual(len(clauses), 2)

    def test_encode_same_and_different_clues(self) -> None:
        """Kiểm tra mã hóa clue SAME và DIFFERENT."""
        clue_same = Clue(id="c_same", type="SAME", target_cells=["A1", "A2"])
        clauses_same = self.encoder.encode_clue(clue_same)
        self.assertGreaterEqual(len(clauses_same), 2)

        clue_diff = Clue(
            id="c_diff", type="DIFFERENT", target_cells=["B1", "B2"]
        )
        clauses_diff = self.encoder.encode_clue(clue_diff)
        self.assertGreaterEqual(len(clauses_diff), 2)

    def test_encode_edge_cases_unsat(self) -> None:
        """Kiểm tra các trường hợp không thể thỏa mãn (UNSAT) trả về [[ ]]."""
        # AT_LEAST k=5 cho 1 ô -> UNSAT
        c_unsat1 = Clue(type="AT_LEAST", target_cells=["A1"], value=5)
        self.assertEqual(self.encoder.encode_clue(c_unsat1), [[]])

        # AT_MOST k=-1 cho 1 ô -> UNSAT
        c_unsat2 = Clue(type="AT_MOST", target_cells=["A1"], value=-1)
        self.assertEqual(self.encoder.encode_clue(c_unsat2), [[]])

    def test_extension_encodings_match_their_semantics(self) -> None:
        """PARITY and COUNT_COMPARE CNF agree with direct evaluation."""
        clues = [
            Clue(
                type="PARITY",
                target_cells=["A1", "A2"],
                value="ODD",
            ),
            Clue(
                type="COUNT_COMPARE",
                left_cells=["A1"],
                right_cells=["A2"],
                operator="GT",
            ),
        ]
        solver = DPLLSolver()
        for clue in clues:
            clauses = self.encoder.encode_clue(clue)
            for a1 in (False, True):
                for a2 in (False, True):
                    assignment = {
                        "A1": "CRIMINAL" if a1 else "INNOCENT",
                        "A2": "CRIMINAL" if a2 else "INNOCENT",
                    }
                    units = [
                        [self.encoder.cell_to_var["A1"] if a1 else -self.encoder.cell_to_var["A1"]],
                        [self.encoder.cell_to_var["A2"] if a2 else -self.encoder.cell_to_var["A2"]],
                    ]
                    self.assertEqual(
                        solver.solve(clauses + units).is_sat,
                        ClueEvaluator.evaluate(clue, assignment),
                    )

    # ------------------------------------------------------------
    # 4. Tests cho Clue Evaluator (Direct Semantic Evaluation)
    # ------------------------------------------------------------

    def test_clue_evaluator(self) -> None:
        """Kiểm tra bộ đánh giá trực tiếp chân lý ClueEvaluator."""
        assign = {"A1": "CRIMINAL", "A2": "INNOCENT", "A3": "CRIMINAL"}

        # FACT
        self.assertTrue(
            ClueEvaluator.evaluate(
                Clue(type="FACT", target_cells=["A1"], value="CRIMINAL"), assign
            )
        )
        self.assertFalse(
            ClueEvaluator.evaluate(
                Clue(type="FACT", target_cells=["A2"], value="CRIMINAL"), assign
            )
        )

        # SAME / DIFFERENT
        self.assertFalse(
            ClueEvaluator.evaluate(
                Clue(type="SAME", target_cells=["A1", "A2"]), assign
            )
        )
        self.assertTrue(
            ClueEvaluator.evaluate(
                Clue(type="DIFFERENT", target_cells=["A1", "A2"]), assign
            )
        )

        # EXACTLY / AT_LEAST / AT_MOST
        self.assertTrue(
            ClueEvaluator.evaluate(
                Clue(type="EXACTLY", target_cells=["A1", "A2", "A3"], value=2),
                assign,
            )
        )
        self.assertTrue(
            ClueEvaluator.evaluate(
                Clue(type="AT_LEAST", target_cells=["A1", "A2", "A3"], value=1),
                assign,
            )
        )

    # ------------------------------------------------------------
    # 5. Test cho KnowledgeBaseSnapshot Packaging
    # ------------------------------------------------------------

    def test_build_snapshot_structure(self) -> None:
        """Kiểm tra hàm đóng gói KnowledgeBaseSnapshot cho DeductiveAgent."""
        clues = [
            Clue(
                id="c1",
                type="EXACT_COUNT",
                target_cells=["A1", "A2"],
                value=1,
            )
        ]
        known = {"A1": "CRIMINAL"}

        snapshot = self.encoder.build_snapshot(
            all_cell_ids=self.cell_ids,
            clues=clues,
            active_clue_ids=["c1"],
            known_statuses=known,
        )

        self.assertGreater(snapshot.clause_count, 0)
        self.assertNotIn("A1", snapshot.unresolved_cell_ids)
        self.assertIn("A2", snapshot.unresolved_cell_ids)


if __name__ == "__main__":
    unittest.main()
