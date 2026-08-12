from dataclasses import dataclass
from .models import SessionState, TRANSITIONS


class InvalidTransition(ValueError):
    pass

@dataclass
class Session:
    session_id: str
    system_id: str
    state: SessionState = SessionState.REQUESTED

    def transition(self, new_state: SessionState) -> None:
        if new_state not in TRANSITIONS[self.state]:
            raise InvalidTransition(f"invalid session transition: {self.state.value} -> {new_state.value}")
        self.state = new_state
