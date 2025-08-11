import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import railtracks as rt
from pydantic import BaseModel, Field
from railtracks import agent_node
from railtracks.llm import (
    AssistantMessage,
    MessageHistory,
    OpenAILLM,
    Parameter,
    UserMessage,
)
from railtracks.nodes.manifest import ToolManifest
from railtracks.rag import RAG

MEMORY_FILE_PATH = os.path.join(os.path.dirname(__file__), "project_memory.json")
print(f"Using memory file path: {MEMORY_FILE_PATH}")


# ----------------------------
# Models
# ----------------------------
class MemoryEntry(BaseModel):
    """A single memory entry."""

    content: str
    timestamp: str
    tags: List[str] = []

    def __str__(self):
        tag_str = ", ".join(self.tags) if self.tags else "No tags"
        return f"[{self.timestamp}] ({tag_str})\n{self.content}"


class ProjectMemory(BaseModel):
    """Project memory with a persistent overview and named entries."""

    overview: Optional[MemoryEntry] = None
    memory_entries: Dict[str, MemoryEntry] = Field(default_factory=dict)
    working_memory: Dict[str, MemoryEntry] = Field(default_factory=dict)


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
            self.memory.memory_entries.update(self.memory.working_memory)
            self.memory.working_memory.clear()
        else:
            self.memory = ProjectMemory()

    def _save_memory(self):
        json.dump(self.memory.model_dump(), open(self.file_path, "w"), indent=2)
        self._init_rag()

    def _init_rag(self):
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

    def get_overview(self) -> str:
        """Get the project overview."""
        if not self.memory.overview:
            return "No overview set."
        return str(self.memory.overview)

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
        self.memory.working_memory[key] = entry
        self._save_memory()

    def list_entries(self) -> List[str]:
        """List all memory entry keys."""
        return list(self.memory.memory_entries.keys())

    def retrieve_entry(self, key: str) -> str:
        entry = self.memory.memory_entries.get(key)
        if not entry:
            return f"No memory found for key '{key}'."
        return str(entry)

    def search(self, query: str, top_k=3) -> str:
        """Search memory entries using RAG."""
        results = self.rag.search(query, top_k=top_k)
        if not results:
            return f"No results for '{query}'."
        output = []
        for res in results:
            output.append(f"[Score: {res.score:.2f}] {res.record.text}")
        return "\n\n".join(output)

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


def set_overview(content: str, tags: List[str] = []):
    """Set or update the project overview."""
    memory.set_overview(content, tags)


def get_overview() -> str:
    """Get the project overview."""
    return memory.get_overview()


def add_entry(key: str, content: str, tags: List[str] = []):
    """Add a new memory entry with a unique key."""
    memory.add_entry(key, content, tags)


# def list_entries() -> List[str]:
#     """List all memory entry keys."""
#     return memory.list_entries()


def retrieve_entry(key: str) -> str:
    """Retrieve a memory entry by key."""
    return memory.retrieve_entry(key)


def search(query: str, top_k: int = 3) -> str:
    """Search memory entries using RAG. Input should be a natural language query."""
    return memory.search(query, top_k)


def delete_entry(key: str) -> bool:
    """Delete a memory entry by key."""
    return memory.delete_entry(key)


memory_functions = {
    rt.function_node(set_overview),
    rt.function_node(get_overview),
    rt.function_node(add_entry),
    # rt.function_node(list_entries),
    rt.function_node(retrieve_entry),
    rt.function_node(search),
    rt.function_node(delete_entry),
}


# ----------------------------
# Memory Agent
# ----------------------------
memory_agent_node = agent_node(
    name="Memory Agent",
    tool_nodes=memory_functions,
    system_message="""You are a Memory Agent that manages project knowledge.
    You can set and retrieve the project overview, add and manage named memory entries,
    and search for relevant information based on user queries. 
    
    Each memory entry you create should have a unique key, content, and optional tags (add relevant tags).
    When creating entries, provide a key that is unique within the project (unless you are updating an existing entry).
    
    You should update the project overview if you receive significant new information from what the current overview is.
    If it is a new project with no overview, you should set it as soon as possible.
    
    Be intelligent about whether a result is actually relevant.
    Always be helpful and focused on the user's needs.
    
    Here is the current list of keys in the project memory:
    {memory_keys}
    
    The project overview is:
    {overview}""",
    llm_model=OpenAILLM(model_name="gpt-4o"),
    manifest=ToolManifest(
        description="Memory Interface that manages project knowledge. Can update the overview or memory entries "
        "of a project, or search for relevant context based on queries.",
        parameters={Parameter(name="request", param_type="string")},
    ),
)


@rt.function_node
def memory_agent(
    request: str,
) -> str:
    """Memory Interface that manages project knowledge. Can update the overview or memory entries "
    "of a project, or search for relevant context based on queries."""
    memory_message_history = rt.context.get("memory_message_history", MessageHistory())
    memory_message_history.append(UserMessage(request))
    response = rt.call_sync(memory_agent_node, memory_message_history).content
    memory_message_history.append(AssistantMessage(response))
    rt.context.put("memory_message_history", memory_message_history)
    return response
