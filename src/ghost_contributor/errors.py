class SafeStop(Exception):
    """An expected, fail-closed policy or operational stop."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
