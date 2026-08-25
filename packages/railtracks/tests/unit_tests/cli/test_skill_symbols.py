"""Every railtracks symbol a bundled skill mentions must actually exist.

Skills are prose shipped to an LLM: when the package renames or removes something,
nothing breaks until an agent follows a stale instruction. This check reads the
*whole* SKILL.md; not only code blocks.

Run as a plain pytest so a stale skill fails in a contributor's checkout, not only in CI.

Only *dotted* mentions are checked: `rt.X`, `railtracks.X`, `from railtracks... import X`.
Bare class names are not — see `test_bare_class_names_are_a_known_blind_spot`.
TODO: (Suggested) Fix this bahaviour by adding a no-bare-name rule for skills.
"""

import re

import railtracks
from railtracks.cli.skills_registry import discover_skills

# `rt.` is the aliased import every skill uses; `railtracks.` is the spelled-out form.
_ATTRIBUTE_PATTERN = re.compile(r"\b(?:rt|railtracks)\.[A-Za-z_][\w.]*")

# Both the one-line and the parenthesised multi-line import forms.
_IMPORT_PATTERN = re.compile(
    r"^[ \t]*from[ \t]+(railtracks[.\w]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n]+)",
    re.MULTILINE,
)

# Prefixes whose resolution depends on an optional extra, used only to name the
# extra in a skip message. The skip itself is decided by the ImportError the absent
# dependency raises, never by this table, so nothing listed here can mask a real gap.
_EXTRA_GATED_PREFIXES = (
    # The whole RAG stack is behind `railtracks[retrieval]`.
    ("railtracks.retrieval", "retrieval"),
    # Portkey's provider wrapper imports its SDK eagerly.
    ("railtracks.llm.models.portkey", "portkey"),
)


def _normalise(symbol: str) -> str:
    """Trim the prose that clings to a symbol: backticks, punctuation, call syntax."""
    symbol = symbol.split("(", 1)[0]
    return symbol.strip("`").rstrip(".,;:!?)]}\"'").rstrip(".")


def _extract_symbols(text: str) -> set[str]:
    """Every dotted railtracks path `text` mentions, as `railtracks.`-rooted names."""
    found = {_normalise(match) for match in _ATTRIBUTE_PATTERN.findall(text)}

    for module, imported in _IMPORT_PATTERN.findall(text):
        # Strip comments per line first: a trailing `# ...` in a parenthesised
        # import would otherwise swallow the newline and hide the next name.
        body = "\n".join(
            line.split("#", 1)[0] for line in imported.strip("()").splitlines()
        )
        for name in body.split(","):
            # `X as Y` binds Y locally; X is the symbol that has to exist.
            name = _normalise(name.split(" as ", 1)[0].strip())
            if name and name != "*":
                found.add(f"{module}.{name}")

    # `rt` is the conventional alias, so both spellings name the same root.
    resolved = {re.sub(r"^rt\.", "railtracks.", s) for s in found}
    return {s for s in resolved if "." in s}


def _extra_for(symbol: str) -> str | None:
    """The extra `symbol` lives behind, if it lives behind one."""
    for prefix, extra in _EXTRA_GATED_PREFIXES:
        if symbol == prefix or symbol.startswith(prefix + "."):
            return extra
    return None


def _resolve(symbol: str) -> tuple[str, str]:
    """Resolve a dotted symbol against the installed package.

    Returns `(status, detail)` where status is "ok", "skipped" or "missing".

    An `ImportError` means the path exists but a dependency behind it does not —
    a missing extra, including one reached through a module-level `__getattr__`
    (`rt.retrieval` re-raises exactly that). Report it as a *skip*.

    An `AttributeError` means every parent segment already resolved and the leaf
    simply is not there. In this package that is never how an absent extra fails —
    the lazy `__getattr__`s let the underlying ImportError through — so it is always
    a real gap and must never be downgraded to a skip.
    """
    obj = railtracks
    for part in symbol.split(".")[1:]:
        try:
            obj = getattr(obj, part)
        except ImportError as e:
            extra = _extra_for(symbol)
            needs = f"railtracks[{extra}]" if extra else "an optional dependency"
            return "skipped", f"needs {needs}: {e}"
        except AttributeError:
            return "missing", f"no attribute {part!r}"
    return "ok", ""


def test_every_symbol_mentioned_by_a_skill_exists():
    """A bundled skill must not name a railtracks symbol the package does not have."""
    missing: dict[str, list[str]] = {}
    skipped: dict[str, list[str]] = {}

    for name, skill in discover_skills().items():
        text = (skill.directory / "SKILL.md").read_text(encoding="utf-8")
        for symbol in sorted(_extract_symbols(text)):
            status, detail = _resolve(symbol)
            if status == "missing":
                missing.setdefault(name, []).append(f"{symbol} — {detail}")
            elif status == "skipped":
                skipped.setdefault(name, []).append(f"{symbol} — {detail}")

    if skipped:
        print("\nSkipped (optional extra not installed):")
        for name, symbols in skipped.items():
            print(f"  {name}:")
            for entry in symbols:
                print(f"    {entry}")

    if missing:
        report = "\n".join(
            f"  {name}:\n" + "\n".join(f"    {entry}" for entry in symbols)
            for name, symbols in missing.items()
        )
        raise AssertionError(
            "Bundled skills reference symbols that do not exist:\n" + report
        )


def test_extraction_finds_symbols_in_prose_and_tables():
    """The extractor must not be a code-block scanner — that is the whole point."""
    text = (
        "| `rt.agent_node` | builds an agent |\n"
        "Use `rt.call`-ing from anywhere, or rt.function_node.\n"
        "```python\n"
        "from railtracks.retrieval.loaders import (\n"
        "    CSVLoader,  # comma-separated values\n"
        "    TextLoader as _T,\n"
        ")\n"
        "rt.llm.OpenAILLM(model='gpt-4o')\n"
        "```\n"
    )

    assert _extract_symbols(text) == {
        "railtracks.agent_node",
        "railtracks.call",
        "railtracks.function_node",
        "railtracks.llm.OpenAILLM",
        "railtracks.retrieval.loaders",
        "railtracks.retrieval.loaders.CSVLoader",
        "railtracks.retrieval.loaders.TextLoader",
    }


def test_bare_class_names_are_a_known_blind_spot():
    """Document the one form this checker does not cover, and why.

    A bare backticked class name carries no namespace, so resolving it means
    searching the package rather than walking a path. Measured against the three
    bundled skills, matching backticked CapWords and resolving against the root
    gives 19 hits and no true positives: 6 are noise (`A`, `B`, `C`, `True`,
    `TypeError`, `BaseModel`) and 13 are real symbols living in submodules —
    `Document`, `Chunk`, `SemanticChunker`, `NodeCreationError` and friends — that
    the skill never imports by name, so its own imports cannot supply the namespace
    either. Closing this needs a real namespace search, not a wider regex.

    If you add that search, delete this test rather than silencing the fallout with
    a per-symbol exception list.
    """
    assert _extract_symbols("| `TerminalLLM` | a removed agent class |\n") == set()

    # The same name is caught the moment it carries a namespace.
    assert _extract_symbols("| `rt.TerminalLLM` | a removed agent class |\n") == {
        "railtracks.TerminalLLM"
    }
    assert _resolve("railtracks.TerminalLLM")[0] == "missing"
