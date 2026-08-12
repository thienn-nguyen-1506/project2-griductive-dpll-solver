"""Game Engine managing hidden ground-truth, player interactions, 
and integration with CNFEncoder & DeductiveAgent.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from core.agent import AgentMetrics, ClassificationResult, DeductiveAgent, KnowledgeBaseSnapshot
from core.encoder import Clue, CNFEncoder


class GameEngine:
    """Manages the interactive game state, hidden solutions, and clue reveals."""

    def __init__(
        self,
        grid_size: int,
        all_cell_ids: List[str],
        hidden_solution: Dict[str, bool],
        hidden_clues: Dict[str, Clue],
        initial_known: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        hidden_solution: Trạng thái thật {'A1': True, 'A2': False, ...} (True = CRIMINAL)
        hidden_clues: Manh mối ẩn dưới lá bài {'A1': Clue_obj, ...}
        initial_known: Ô đã công khai từ đầu {'A1': 'CRIMINAL', ...}
        """
        self.grid_size = grid_size
        self.all_cell_ids = all_cell_ids
        self._solution = hidden_solution
        self._clues = hidden_clues
        
        # Trạng thái công khai trên bàn cờ
        self.known_statuses: Dict[str, str] = initial_known.copy() if initial_known else {}
        self.revealed_cards: Set[str] = set()

        self.encoder = CNFEncoder()
        self.agent = DeductiveAgent()

    # ---------------------------------------------------------------------------
    # Core Game Logic (Player / Ground Truth)
    # ---------------------------------------------------------------------------

    def check_verdict(self, char_id: str, claimed_status: str) -> bool:
        """Kiểm tra câu trả lời người chơi chọn ('CRIMINAL'/'INNOCENT') có đúng đáp án không."""
        if char_id not in self._solution:
            return False
        
        is_criminal_truth = self._solution[char_id]
        expected_status = "CRIMINAL" if is_criminal_truth else "INNOCENT"
        return claimed_status == expected_status

    def reveal_card(self, char_id: str) -> Optional[Clue]:
        """Lật bài tại ô char_id và kích hoạt manh mối ẩn."""
        if char_id in self._clues:
            self.revealed_cards.add(char_id)
            return self._clues[char_id]
        return None

    # ---------------------------------------------------------------------------
    # Agent & CNF Integration
    # ---------------------------------------------------------------------------

    def get_kb_snapshot(self) -> KnowledgeBaseSnapshot:
        """Tạo KnowledgeBaseSnapshot từ danh sách manh mối đã lật và trạng thái ô đã biết."""
        active_clues = [self._clues[cid] for cid in self.revealed_cards if cid in self._clues]
        active_clue_ids = [c.id for c in active_clues]

        return self.encoder.build_snapshot(
            all_cell_ids=self.all_cell_ids,
            clues=active_clues,
            active_clue_ids=active_clue_ids,
            known_statuses=self.known_statuses,
        )

    def deduce_next_move(self) -> Tuple[Optional[Tuple[str, str]], ClassificationResult]:
        """Cho Agent suy luận bước tiếp theo dựa trên thông tin công khai hiện tại.
        
        Returns:
            ((cell_id, status), result) nếu tìm thấy ô ép buộc.
            (None, result) nếu chưa đủ thông tin ép buộc ô nào.
        """
        snapshot = self.get_kb_snapshot()
        forced_cell, result = self.agent.deduce_one_step(snapshot)

        # Nếu suy luận ra nước đi bắt buộc, tự động cập nhật vào ô đã biết
        if forced_cell:
            cell_id, status = forced_cell
            self.known_statuses[cell_id] = status

        return forced_cell, result