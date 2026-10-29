from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadFailure:
    """A source that a loader could not read.

    Yielded by ``BaseDocumentLoader.astream()`` in place of the documents a
    source would have produced, so one unreadable file or object does not end
    the stream. Documents the source yielded before it failed are kept; the
    rest of that source is skipped.

    Attributes:
        source: The file path, object URI, or other identifier of the source,
            in the same form the loader uses for ``Document.source``.
        error: The exception raised while reading the source.
    """

    source: str
    error: Exception
