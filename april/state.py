"""States describe active I/O operations, never an interpretation of reasoning."""
from enum import StrEnum


class State(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


ALLOWED = {
    State.IDLE: {State.LISTENING, State.THINKING},
    State.LISTENING: {State.TRANSCRIBING},
    State.TRANSCRIBING: {State.THINKING},
    State.THINKING: {State.SPEAKING},
    State.SPEAKING: set(),
    State.ERROR: set(),
}


class StateMachine:
    def __init__(self):
        self.state = State.IDLE

    def move(self, target: State):
        # Cancellation, completion and errors may terminate any operation.
        if target not in {State.IDLE, State.ERROR} and target not in ALLOWED[self.state]:
            raise ValueError(f"Invalid state transition: {self.state} -> {target}")
        self.state = target
