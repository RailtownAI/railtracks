"""MkDocs hooks for generating derived documentation files."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from markdown import Markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

_GLOSSARY_TERM = re.compile(r"^### (?P<term>.+?)\s*$", re.MULTILINE)

# Under a glossary heading, `<!-- tooltip: agent node, agent nodes -->` lists extra
# spellings that carry the term's tooltip, and `<!-- tooltip: none -->` gives the
# term no tooltip at all.
_TOOLTIP_DIRECTIVE = re.compile(
    r"^<!--\s*tooltip:\s*(?P<forms>.*?)\s*-->\s*$", re.MULTILINE
)

# Elements that label the content beneath them, where a tooltip only repeats it.
_LABEL_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "summary", "label"})


def _plain_text(markdown: str) -> str:
    """Strip the inline markup `abbr` definitions cannot carry.

    Abbreviation definitions render as a plain `title` attribute, so links, emphasis
    and code spans have to be flattened to their text.
    """
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)  # links -> link text
    text = text.replace("`", "")
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)  # bold / emphasis
    return " ".join(text.split())


def _first_sentence(paragraph: str) -> str:
    """Return the paragraph's opening sentence, keeping its terminating period."""
    match = re.search(r"^.*?[.!?](?=\s|$)", paragraph)
    return (match.group(0) if match else paragraph).strip()


def _tooltip_forms(term: str, body: str) -> list[str]:
    """Return the spellings that carry a glossary term's tooltip.

    The heading text always does, unless the entry opts out with
    `<!-- tooltip: none -->`. Any other spelling, such as a lowercase or plural
    form, is listed in the entry's `<!-- tooltip: ... -->` directive.
    """
    directive = _TOOLTIP_DIRECTIVE.search(body)
    if directive is None:
        return [term]
    forms = [form.strip() for form in directive.group("forms").split(",")]
    forms = [form for form in forms if form]
    if forms == ["none"]:
        return []
    return [term, *forms]


def _glossary_tooltips(glossary: Path) -> str:
    """Build the `abbr` definition list that gives glossary terms their tooltips.

    Generated rather than hand-written so the tooltip a reader hovers and the entry
    on the glossary page cannot drift apart.
    """
    text = glossary.read_text(encoding="utf-8").replace("\r\n", "\n")
    matches = list(_GLOSSARY_TERM.finditer(text))

    lines = [
        "<!-- Generated from docs/glossary.md by scripts/mkdocs_hooks.py. Do not edit. -->",
        "",
    ]
    for current, following in zip(matches, matches[1:] + [None]):
        term = current.group("term")
        end = following.start() if following is not None else len(text)
        body = text[current.end() : end].strip()

        forms = _tooltip_forms(term, body)
        prose = _TOOLTIP_DIRECTIVE.sub("", body).strip()
        if not forms or not prose:
            continue

        definition = _first_sentence(_plain_text(prose.split("\n\n")[0]))
        if definition:
            lines.extend(f"*[{form}]: {definition}" for form in forms)

    return "\n".join(lines) + "\n"


def _is_label(element: Element) -> bool:
    """Return True if the element is a heading, summary, tab label or admonition title."""
    if element.tag in _LABEL_TAGS:
        return True
    classes = (element.get("class") or "").split()
    return element.tag == "p" and "admonition-title" in classes


def _unwrap(parent: Element, child: Element) -> None:
    """Replace `child` with its text, keeping the surrounding text in order."""
    text = (child.text or "") + (child.tail or "")
    index = list(parent).index(child)
    if index == 0:
        parent.text = (parent.text or "") + text
    else:
        previous = parent[index - 1]
        previous.tail = (previous.tail or "") + text
    parent.remove(child)


class _FirstMentionTooltips(Treeprocessor):
    """Keep only the first tooltip for each glossary term on a page.

    Tooltips inside a heading, summary, tab label or admonition title are removed
    outright and do not count as the first mention. See the "Keywords and the
    glossary" section of `docs/documentation/getting_started/contributing_docs.md`.
    """

    def run(self, root: Element) -> None:
        self._prune(root, seen=set(), in_label=False)

    def _prune(self, parent: Element, seen: set[str], in_label: bool) -> None:
        for child in list(parent):
            if child.tag != "abbr":
                self._prune(child, seen, in_label or _is_label(child))
                continue
            definition = child.get("title", "")
            if in_label or definition in seen:
                _unwrap(parent, child)
            else:
                seen.add(definition)


class _GlossaryTooltipExtension(Extension):
    """Markdown extension that limits glossary tooltips to one per term per page."""

    def extendMarkdown(self, md: Markdown) -> None:  # noqa: N802
        # After `abbr` (7) has created the tooltips, before `toc` (5) reads headings.
        md.treeprocessors.register(
            _FirstMentionTooltips(md), "first_mention_tooltips", 6
        )


def _write_if_changed(path: Path, content: str) -> None:
    """Write only on a real change, so the file's mtime stays put.

    `mkdocs serve` watches the docs directory. Rewriting a file there on every build
    would register as a change and kick off another build, looping forever.
    """
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _api_reference_is_fresh(src_dir: Path, output_dir: Path) -> bool:
    """Return True if pdoc's generated HTML is newer than every source .py file.

    Only pdoc's own output (the ``*.html`` files it rewrites on every run) is
    considered. Other files that may live in the output dir — a static ``.gitignore``,
    or ``.md`` artifacts from a separate step — are NOT regenerated by pdoc, so
    including them would peg the comparison to their (old) mtime and make this always
    report "stale". That reruns pdoc on every build, and because the output lives under
    the watched ``docs/`` dir it triggers an infinite ``mkdocs serve`` reload loop.
    """
    output_files = [f for f in output_dir.rglob("*.html") if f.is_file()]
    if not output_files:
        return False
    newest_src = max(f.stat().st_mtime for f in src_dir.rglob("*.py"))
    oldest_out = min(f.stat().st_mtime for f in output_files)
    return oldest_out > newest_src


def _generate_api_reference(repo_root: Path, output_dir: Path) -> None:
    # Wipe the output dir so HTML for removed modules doesn't linger. Orphaned files
    # pin the freshness check's `min(mtime)` to an old date and cause every build to
    # regenerate, which triggers `mkdocs serve`'s watcher into an infinite reload loop.
    if output_dir.exists():
        shutil.rmtree(output_dir)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pdoc",
            "packages/railtracks/src/railtracks",
            "--output-dir",
            str(output_dir),
            "-d",
            "google",
            "--include-undocumented",
            "--logo",
            "https://raw.githubusercontent.com/RailtownAI/railtracks/main/docs/assets/logo.svg",
        ],
        check=True,
        cwd=repo_root,
    )


def on_config(config: MkDocsConfig) -> MkDocsConfig:
    """Register the Markdown extension that limits glossary tooltips per page."""
    config.markdown_extensions.append(_GlossaryTooltipExtension())  # type: ignore[arg-type]
    return config


def on_pre_build(config, **kwargs):
    """Regenerate the derived documentation files before each build.

    Skips pdoc entirely when output is already newer than all source files,
    which prevents MkDocs' watcher from detecting a spurious change and
    triggering an infinite-rebuild loop during `mkdocs serve`.
    """
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "packages" / "railtracks" / "src" / "railtracks"
    output_dir = repo_root / "docs" / "api_reference"

    glossary = repo_root / "docs" / "glossary.md"
    if glossary.exists():
        _write_if_changed(
            repo_root / "docs" / "includes" / "glossary_tooltips.md",
            _glossary_tooltips(glossary),
        )

    if _api_reference_is_fresh(src_dir, output_dir):
        return

    _generate_api_reference(repo_root, output_dir)
