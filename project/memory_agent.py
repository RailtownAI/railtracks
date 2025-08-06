import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import railtracks as rt
from pydantic import BaseModel, Field
from railtracks import agent_node
from railtracks.rag import RAG

MEMORY_FILE_PATH = os.path.join(os.path.dirname(__file__), "project_memory.json")


# ----------------------------
# Models
# ----------------------------
class MemoryEntry(BaseModel):
    """A single memory entry."""

    content: str
    timestamp: str
    tags: List[str] = []


class ProjectMemory(BaseModel):
    """Project memory with a persistent overview and named entries."""

    overview: Optional[MemoryEntry] = None
    memory_entries: Dict[str, MemoryEntry] = Field(default_factory=dict)


# ----------------------------
# Persistent Context
# ----------------------------
class PersistentMemoryContext:
    def __init__(
        self, file_path: str = MEMORY_FILE_PATH, embed_model="text-embedding-3-small"
    ):
        self.file_path = file_path
        self.embed_model = embed_model
        self._load_memory()
        self._init_rag()

    def _load_memory(self):
        if os.path.exists(self.file_path):
            self.memory = ProjectMemory(**json.load(open(self.file_path)))
        else:
            self.memory = ProjectMemory()

    def _save_memory(self):
        json.dump(self.memory.model_dump(), open(self.file_path, "w"), indent=2)
        self._init_rag()

    def _init_rag(self, **rag_config):
        docs = self._memory_to_documents()
        self.rag = RAG(docs=docs, embed_config={"model": self.embed_model})
        self.rag.embed_all()

    def _memory_to_documents(self) -> List[str]:
        docs = []
        if self.memory.overview:
            docs.append(
                f"OVERVIEW\nTAGS: {', '.join(self.memory.overview.tags)}\nCONTENT:\n{self.memory.overview.content}"
            )
        for key, entry in self.memory.memory_entries.items():
            docs.append(
                f"KEY: {key}\nTAGS: {', '.join(entry.tags)}\nCONTENT:\n{entry.content}"
            )
        return docs

    def get_overview(self) -> MemoryEntry:
        """Get the project overview."""
        return self.memory.overview

    def set_overview(self, content: str, tags: List[str] = []):
        """Set or update the project overview."""
        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now().isoformat(),
            tags=tags,
        )
        self.memory.overview = entry
        self._save_memory()

    def add_entry(self, key: str, content: str, tags: List[str] = []):
        """Add a new memory entry with a unique key."""
        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now().isoformat(),
            tags=tags,
        )
        self.memory.memory_entries[key] = entry
        self._save_memory()

    def list_entries(self) -> List[str]:
        """List all memory entry keys."""
        return list(self.memory.memory_entries.keys())

    def retrieve_entry(self, key: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by key."""
        return self.memory.memory_entries.get(key)

    def search(self, query: str, top_k=3):
        """Search memory entries using RAG."""
        return self.rag.search(query, top_k=top_k)

    def delete_entry(self, key: str) -> bool:
        """Delete a memory entry by key."""
        if key in self.memory.memory_entries:
            del self.memory.memory_entries[key]
            self._save_memory()
            return True
        return False


# ----------------------------
# Memory Functions
# ----------------------------
memory = PersistentMemoryContext()
memory_functions = {
    rt.function_node(memory.set_overview),
    rt.function_node(memory.get_overview),
    rt.function_node(memory.add_entry),
    rt.function_node(memory.list_entries),
    rt.function_node(memory.retrieve_entry),
    rt.function_node(memory.search),
    rt.function_node(memory.delete_entry),
}


# ----------------------------
# Memory Agent
# ----------------------------
memory_agent = agent_node(name="Memory Agent", tool_nodes=memory_functions)

# ----------------------------
# Memory Functions
# ----------------------------
