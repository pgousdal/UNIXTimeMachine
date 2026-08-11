from dataclasses import dataclass
from .models import SessionState

@dataclass
class Session:
    session_id: str
    system_id: str
    state: SessionState = SessionState.REQUESTED

    def transition(self, new_state: SessionState) -> None:
        self.state = new_state
