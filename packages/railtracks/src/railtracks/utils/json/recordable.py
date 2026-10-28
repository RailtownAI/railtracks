from typing import Any, Callable, Protocol, runtime_checkable


class MediaSink(Protocol):
    """Stores media bytes by content hash for the event record."""

    def save(self, sha256: str, size: int, data: Callable[[], bytes]) -> None:
        """Store media bytes under their content hash.

        Args:
            sha256: The hex SHA-256 of the bytes.
            size: The number of bytes, checked against any size limit before
                `data` is called.
            data: Returns the bytes. Only called when they still need writing.
        """
        ...


@runtime_checkable
class Recordable(Protocol):
    """An object whose shape in the event record differs from its `encode()`.

    `encode()` also feeds the session JSON, so anything that should look different
    in the JSONL events implements `record()` instead of changing `encode()`.
    """

    def record(self, media: MediaSink | None) -> dict[str, Any]: ...
