def format_multiline_for_markdown(mk_text: str):
    """
    Format a multiline string for markdown by adding a space at the beginning of each line.
    """
    markdown_chars = [
        "\\",
        "`",
        "*",
        "_",
        "{",
        "}",
        "[",
        "]",
        "(",
        ")",
        "#",
        "+",
        "-",
        ".",
        "!",
    ]

    # Escape each special character
    for char in markdown_chars:
        mk_text = mk_text.replace(char, "\\" + char)
    return mk_text.replace("\n", "<br>")
    # add the escape character to end of each line except for the last one


if __name__ == "__main__":
    text = "Role: user \n content: Hello world"
    text = format_multiline_for_markdown(text)
    print(text)
