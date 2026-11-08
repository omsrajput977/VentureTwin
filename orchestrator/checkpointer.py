import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from state.shared_state import WorkflowState

class SQLiteCheckpointer:
    def __init__(self, db_path: str = "venturetwin_checkpoints.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    decision_id TEXT,
                    task_id TEXT,
                    timestamp TEXT,
                    state_json TEXT,
                    PRIMARY KEY (decision_id, task_id)
                )
            """)
            conn.commit()

    def save_checkpoint(self, state: WorkflowState, task_id: str) -> None:
        with self._get_connection() as conn:
            state_json = state.model_dump_json()
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints (decision_id, task_id, timestamp, state_json)
                VALUES (?, ?, ?, ?)
            """, (state.decision.id, task_id, now, state_json))
            conn.commit()

    def load_latest_checkpoint(self, decision_id: str) -> Optional[WorkflowState]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT state_json FROM checkpoints
                WHERE decision_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (decision_id,))
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return WorkflowState.model_validate(data)
            return None

    def get_completed_tasks(self, decision_id: str) -> List[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id FROM checkpoints
                WHERE decision_id = ?
            """, (decision_id,))
            return [r[0] for r in cursor.fetchall()]

    def clear(self, decision_id: Optional[str] = None) -> None:
        with self._get_connection() as conn:
            if decision_id:
                conn.execute("DELETE FROM checkpoints WHERE decision_id = ?", (decision_id,))
            else:
                conn.execute("DELETE FROM checkpoints")
            conn.commit()

