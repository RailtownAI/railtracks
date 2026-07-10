from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import railtracks as rt
from railtracks.built_nodes.concrete.function_base import RTFunction
from railtracks.utils.logging.create import get_rt_logger

from .._base import ToolSet

if TYPE_CHECKING:
    from railtracks.retrieval.stores.key_value import KeyValueStore, SearchAlgorithm

logger = get_rt_logger(__name__)


def _default_store() -> KeyValueStore:
    from railtracks.retrieval.stores.key_value import InMemoryKeyValueStore

    return InMemoryKeyValueStore()


def _default_search() -> SearchAlgorithm:
    from railtracks.retrieval.stores.key_value import LexicalSearch

    return LexicalSearch()


class KeyValueMemoryToolSet(ToolSet):
    """Prebuilt key-value memory tools for an agent.

    Gives an agent a persistent, exact-match scratch pad: save a fact under a
    key, read it back later, forget it, list everything, or search. State lives
    in the injected :class:`~railtracks.retrieval.stores.key_value.KeyValueStore`
    (defaults to an in-process :class:`InMemoryKeyValueStore`). Pass a store
    constructed with a ``snapshot_path`` for persistence across runs::

        store = InMemoryKeyValueStore(snapshot_path="memory.json")
        toolset = KeyValueMemoryToolSet(store=store)

    All memory in a toolset shares one namespace. To keep separate memories for
    different agents, give each its own ``KeyValueMemoryToolSet`` (and its own
    store).

    Args:
        store: Backing key-value store. Defaults to a fresh, ephemeral
            ``InMemoryKeyValueStore``.
        search: Ranking algorithm used by ``search_memories``. Defaults to
            ``LexicalSearch()``. Pass a ``LexicalSearch(LexicalSearchConfig(...))``
            to tune the ranking weights, or any other
            :class:`~railtracks.retrieval.stores.key_value.SearchAlgorithm`
            implementation to swap the algorithm entirely.
        on_change: Optional callback fired after every mutation, letting an
            outer system react (push to a UI, mirror to a database, log).
            Called as ``on_change(key, value)`` where ``value`` is the new
            value on a save and ``None`` on a forget. Exceptions raised by the
            callback are logged and swallowed so they never break a tool call.
    """

    def __init__(
        self,
        store: KeyValueStore | None = None,
        search: SearchAlgorithm | None = None,
        on_change: Callable[[str, str | None], None] | None = None,
    ) -> None:
        self.store: KeyValueStore = store if store is not None else _default_store()
        self._search: SearchAlgorithm = search if search is not None else _default_search()
        self.on_change = on_change

    def _notify(self, key: str, value: str | None) -> None:
        if self.on_change is None:
            return
        try:
            self.on_change(key, value)
        except Exception as e:
            logger.error(f"Error in on_change callback for key {key!r}: {e}")

    async def remember(self, key: str, value: str) -> str:
        """Save a fact to memory under a key, for recall later.

        If the key already holds a value it is overwritten, so use a stable,
        descriptive key (e.g. "user_timezone", "project_deadline") and re-call
        remember() to update a fact.

        Args:
            key: Short, stable identifier for the fact (used to recall it).
            value: The fact to store, as a self-contained string.

        Returns:
            A confirmation that the fact was stored.
        """
        await self.store.set(key, value)
        self._notify(key, value)
        return f"Remembered '{key}': {value}"

    async def recall(self, key: str) -> str:
        """Recall the value previously stored under a key.

        Args:
            key: The exact key the fact was stored under.

        Returns:
            The stored value, or a message saying nothing is stored under that
            key. Use list_memories() if you are unsure of the exact key.
        """
        value = await self.store.get(key)
        if value is None:
            return f"No memory found under key '{key}'."
        return value

    async def forget(self, key: str) -> str:
        """Delete the fact stored under a key.

        Args:
            key: The key to remove. Forgetting a key that does not exist is a
                no-op and is reported as such.

        Returns:
            A confirmation describing what happened.
        """
        existed = await self.store.get(key) is not None
        await self.store.delete(key)
        self._notify(key, None)
        if existed:
            return f"Forgot '{key}'."
        return f"Nothing was stored under '{key}'; nothing to forget."

    async def list_memories(self) -> str:
        """List every key and value currently held in memory.

        Returns:
            A newline-separated "key: value" listing, or a message saying
            memory is empty.
        """
        items = await self.store.items()
        if not items:
            return "No memories stored."
        return "\n".join(f"- {key}: {value}" for key, value in items.items())

    async def list_keys(self) -> str:
        """List just the keys currently held in memory, without their values.

        Prefer this over list_memories() to see what is stored without pulling
        every value into context; then recall(key) only the ones you need.

        Returns:
            A newline-separated list of keys, or a message saying memory is
            empty.
        """
        keys = await self.store.keys()
        if not keys:
            return "No memories stored."
        return "\n".join(f"- {key}" for key in keys)

    async def search_memories(self, query: str) -> str:
        """Search stored memories for relevance to a query across keys and values.

        Use this when you remember roughly what a fact was about but not the
        exact key. Ranking favors exact and substring key matches, but also
        catches value hits, multi-word queries, and near-miss typos — so it
        finds more than a plain substring search would.

        Args:
            query: Free-text search string.

        Returns:
            Matching "key: value" entries ranked by relevance, or a message
            saying nothing matched.
        """
        items = await self.store.items()
        hits = self._search.search(items, query)
        if not hits:
            return f"No memories matched '{query}'."
        return "\n".join(f"- {key}: {value}" for key, value, _score in hits)

    @classmethod
    def prompt(cls) -> str:
        return (
            "Use the memory tools to remember facts across the conversation. "
            "Call remember(key, value) to save a fact under a short, stable, descriptive key; "
            "re-calling remember() with the same key overwrites the old value. "
            "Call recall(key) to read a fact back, and forget(key) to delete one. "
            "If you are unsure of the exact key, call search_memories() to find related entries, "
            "list_keys() to see what is stored without pulling in every value, "
            "or list_memories() to see everything stored. "
            "Save anything the user tells you that may be useful later (preferences, names, goals, "
            "constraints), and recall before asking the user to repeat themselves."
        )

    def tool_set(self) -> list[RTFunction]:
        functions = [
            self.remember,
            self.recall,
            self.forget,
            self.list_keys,
            self.list_memories,
            self.search_memories,
        ]
        return [rt.function_node(func) for func in functions]
