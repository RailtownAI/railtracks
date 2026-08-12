import logging
import string
from typing import Any, Mapping

_PARSER = string.Formatter()
_logger = logging.getLogger("RT.prompt_injection")


def escape_braces(text: str) -> str:
    """
    Escape the braces in `text` so that prompt injection treats it as data.

    Apply this to untrusted or arbitrary strings before embedding them in a message that
    will have context values injected into it. Injecting the returned string yields
    `text` back unchanged.

    Args:
        text: The string to escape.

    Returns:
        `text` with every `{` and `}` doubled.
    """
    return text.replace("{", "{{").replace("}", "}}")


def _as_written(
    field_name: str, conversion: str | None, format_spec: str | None
) -> str:
    """Rebuild the original `{...}` text of a placeholder that was not filled."""
    suffix = f"!{conversion}" if conversion else ""
    if format_spec:
        suffix += f":{format_spec}"
    return f"{{{field_name}{suffix}}}"


def fill_template(template: str, values: Mapping[str, Any]) -> str:
    """
    Fill the `{key}` placeholders in `template` with entries from `values`.

    Only a bare key is filled. A placeholder that uses attribute access, indexing, a
    conversion or a format spec is left in the output exactly as it was written, as is a
    key with no matching entry in `values`. `{{` and `}}` become single braces. A
    template whose braces do not parse is returned unchanged.

    Args:
        template: The string to fill.
        values: The values available to fill placeholders with.

    Returns:
        The filled string.
    """
    try:
        placeholders = list(_PARSER.parse(template))
    except ValueError:
        return template

    filled: list[str] = []
    left_as_written: list[str] = []
    for literal_text, field_name, format_spec, conversion in placeholders:
        filled.append(literal_text)
        if field_name is None:
            continue

        # A bare key is the only form we resolve. Anything else -- `{a.b}`, `{a[b]}`,
        # `{a!r}`, `{a:spec}`, or the positional `{}` -- would hand control of an
        # attribute or item lookup to whoever wrote the template.
        if (
            conversion is not None
            or format_spec
            or not field_name
            or "." in field_name
            or "[" in field_name
        ):
            as_written = _as_written(field_name, conversion, format_spec)
            left_as_written.append(as_written)
            filled.append(as_written)
            continue

        try:
            filled.append(str(values[field_name]))
        except Exception:
            filled.append(_as_written(field_name, conversion, format_spec))

    if left_as_written:
        _logger.warning(
            "Left %s prompt placeholder(s) as written because only bare {key} "
            "placeholders are filled: %s",
            len(left_as_written),
            ", ".join(left_as_written),
        )

    return "".join(filled)


class ValueDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"  # Return the placeholder if not found
