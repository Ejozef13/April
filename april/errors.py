"""Safe, actionable errors that never include prompts or remote response bodies."""


class BackendError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
