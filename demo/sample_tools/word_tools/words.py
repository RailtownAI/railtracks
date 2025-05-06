from typing import List


def check_chars(input: str, char: str) -> int:
    """
    Count the number of instances of a character in a word

    Args:
        input (str): The word to be checked
        char (str): The character to count instances of

    Returns:
        the number of instances of the charcter
    """
    return input.count(char)


