from copy import deepcopy

import railtracks as rt
from railtracks.vector_stores.vector_store_base import VectorStore


class RagConfig:
    """
    Configuration object for Retrieval-Augmented Generation (RAG).
    """

    def __init__(self, vector_store: VectorStore, top_k: int = 3) -> None:
        self.vector_store = vector_store
        self.top_k = top_k


def _parse_message_combos(message_history: rt.llm.MessageHistory):
    """
    Breaks the message history into (user → assistants) grouped chunks suitable
    for RAG search queries.

    The algorithm:
        • Removes system messages.
        • Iterates through remaining messages.
        • Each user message starts a new combo.
        • All assistant messages following it (until the next user message)
          are grouped together.

    Args:
        message_history (MessageHistory):
            Sequence of LLM messages from the railtracks interface.

    Returns:
        list[tuple[str, str]]:
            A list of (user_text, assistant_text) pairs, where each value is a
            prepared string created via `_prepare_messages`.

    Raises:
        AssertionError:
            If a non-user message is encountered at a position where a user
            message is expected.
    """
    search_chunks = []

    idx = 0
    system_message_less = [
        x for x in message_history if x.role != rt.llm.message.Role.system
    ]

    while True:
        user_message = None
        assistants = []
        assert system_message_less[idx].role == rt.llm.message.Role.user

        user_message = system_message_less[idx]
        idx_offset = 1

        while True:
            if idx + idx_offset == len(system_message_less):
                break

            message = system_message_less[idx + idx_offset]

            if message.role == rt.llm.message.Role.user:
                break

            assistants.append(message)
            idx_offset += 1  # fixed bug: was "=+ 1"

        search_chunks.append(
            (_prepare_messages(user_message), _prepare_messages(assistants))
        )

        idx = idx + idx_offset

        if idx >= len(system_message_less):
            break

    return search_chunks


def update_context(
    message_history: rt.llm.MessageHistory,
    vs: rt.vector_stores.vector_store_base.VectorStore,
    top_k: int = 3,
):
    """
    Performs a RAG-style context injection into a message history.

    Steps:
        1. Deep-copy the message history (original remains untouched).
        2. Convert the history into grouped (user → assistants) chunks.
        3. Generate all possible contiguous subsequences of these chunks.
        4. Search the vector store using these sequences.
        5. Collect all unique returned results.
        6. Construct an injection text block from these results.
        7. Prepend a new user message containing the contextual information.

    Args:
        message_history (MessageHistory):
            The original message history to augment.
        vs (VectorStore):
            A vector store instance implementing `.search(texts, top_k)`.
        top_k (int):
            Number of results to retrieve from each search query.

    Returns:
        MessageHistory:
            A new message history with prepended retrieved context.
    """
    message_history = deepcopy(message_history)

    parsed_messages = _parse_message_combos(message_history)
    chunks_to_search = _random_contiguous_subsequence(parsed_messages)

    chunks = {}
    results = vs.search(chunks_to_search, top_k=top_k)

    for r in results:
        if isinstance(r, list):
            for item in r:
                if item.id not in chunks:
                    chunks[item.id] = item.content
        else:
            chunks[r.id] = r.content

    injection_str = (
        "\n\n\n------------------------------------------------------\n".join(
            list(chunks.values())
        )
    )

    fillable_system_message = f"You may find the following useful:\n{injection_str}"

    message_history.insert(0, rt.llm.UserMessage(fillable_system_message))
    return message_history


def _prepare_messages(messages: list[rt.llm.Message] | rt.llm.Message):
    """
    Converts one or many message objects into a newline-joined string.

    Args:
        messages (Message | list[Message]):
            One message or a list of messages.

    Returns:
        str:
            A readable text representation of the message(s).
    """
    if isinstance(messages, list):
        return "\n".join([str(x) for x in messages])
    else:
        return str(messages)


def _random_contiguous_subsequence(seq: list[tuple[str, str]]):
    """
    Generates all possible contiguous subsequences from a list of message pairs,
    flattening each subsequence into a single string.

    Example:
        Input:
            [(U1, A1), (U2, A2)]
        Output:
            [
                "U1\nA1",
                "U1\nA1\nU2\nA2",
                "U2\nA2"
            ]

    Args:
        seq (list[tuple[str, str]]):
            List of (user_text, assistant_text) pairs.

    Returns:
        list[str]:
            Every possible contiguous combination of messages, each as one string.
    """
    new_seq: list[str] = []
    for i in range(len(seq)):
        for j in range(i, len(seq)):
            texts = []
            for idx in range(i, j + 1):
                texts.append(seq[idx][0])
                texts.append(seq[idx][1])
            new_seq.append("\n".join(texts))

    return new_seq
