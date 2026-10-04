class LLMError(RuntimeError):
    """Raised when any model backend fails, so the router can fall back."""