class VisualExtraRequiredError(ImportError):
    """Raised when FastAPI/uvicorn-backed optional components are used without installing extras."""

    def __init__(self, message: str | None = None) -> None:
        default = (
            "This feature requires optional visual dependencies. "
            "Install with: pip install 'railtracks[visual]'."
        )
        super().__init__(message or default)
