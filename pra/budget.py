"""Step, token, and time limits checked on every loop iteration (FR-17)."""
import time
from dataclasses import dataclass, field


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    max_steps: int = 30
    max_tokens: int = 200_000
    max_seconds: float = 300.0
    steps: int = 0
    tokens: int = 0
    started: float = field(default_factory=time.monotonic)

    def charge(self, tokens: int = 0) -> None:
        self.steps += 1
        self.tokens += tokens
        self.check()

    def check(self) -> None:
        if self.steps > self.max_steps:
            raise BudgetExceeded("step limit reached")
        if self.tokens > self.max_tokens:
            raise BudgetExceeded("token limit reached")
        if time.monotonic() - self.started > self.max_seconds:
            raise BudgetExceeded("time limit reached")
