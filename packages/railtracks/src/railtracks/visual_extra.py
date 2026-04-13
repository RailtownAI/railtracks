#   -------------------------------------------------------------
#   Copyright (c) Railtown AI. All rights reserved.
#   Licensed under the MIT License. See LICENSE in project root for information.
#   -------------------------------------------------------------


class VisualExtraRequiredError(ImportError):
    """Raised when FastAPI/uvicorn-backed optional components are used without installing extras."""

    def __init__(self, message: str | None = None) -> None:
        default = (
            "This feature requires optional visual dependencies. "
            "Install with: pip install 'railtracks[visual]' "
            "(or 'railtracks[cli]' for backward compatibility)."
        )
        super().__init__(message or default)
