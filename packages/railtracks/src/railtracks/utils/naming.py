"""
Naming utilities for RailTracks nodes and functions.

This module provides utilities for converting between different naming conventions,
particularly for ensuring consistent Title Case names for RailTracks nodes while
maintaining valid snake_case identifiers for tool calls.
"""



def snake_case_to_title_case(snake_case_name: str) -> str:
    """
    Convert a snake_case name to Title Case.

    Args:
        snake_case_name (str): A string in snake_case format (e.g., "my_function_name")

    Returns:
        str: The name converted to Title Case (e.g., "My Function Name")

    Examples:
        >>> snake_case_to_title_case("test_function")
        "Test Function"
        >>> snake_case_to_title_case("number_of_chars")
        "Number Of Chars"
        >>> snake_case_to_title_case("calculate_sum")
        "Calculate Sum"
        >>> snake_case_to_title_case("simple")
        "Simple"
    """
    # Split by underscores and capitalize each word
    words = snake_case_name.split("_")
    title_case_words = [word.capitalize() for word in words if word]
    return " ".join(title_case_words)


def title_case_to_snake_case(title_case_name: str) -> str:
    """
    Convert a Title Case name to snake_case.

    Args:
        title_case_name (str): A string in Title Case format (e.g., "My Function Name")

    Returns:
        str: The name converted to snake_case (e.g., "my_function_name")

    Examples:
        >>> title_case_to_snake_case("Test Function")
        "test_function"
        >>> title_case_to_snake_case("Number Of Chars")
        "number_of_chars"
        >>> title_case_to_snake_case("Calculate Sum")
        "calculate_sum"
        >>> title_case_to_snake_case("Simple")
        "simple"
    """
    # Split by spaces and join with underscores, then lowercase
    words = title_case_name.split()
    snake_case_words = [word.lower() for word in words if word]
    return "_".join(snake_case_words)


def is_title_case(name: str) -> bool:
    """
    Check if a name is in Title Case format.

    Title Case means each word starts with a capital letter and is separated by spaces.

    Args:
        name (str): The name to check

    Returns:
        bool: True if the name is in Title Case, False otherwise

    Examples:
        >>> is_title_case("Test Function")
        True
        >>> is_title_case("test_function")
        False
        >>> is_title_case("testFunction")
        False
        >>> is_title_case("Simple")
        True
    """
    if not name:
        return False

    # Check if name contains spaces (Title Case should have spaces between words)
    # and each word starts with uppercase letter
    words = name.split()
    if len(words) == 1:
        # Single word should start with uppercase
        return (
            name[0].isupper() and name[1:].islower()
            if len(name) > 1
            else name.isupper()
        )

    # Multiple words: each should start with uppercase, rest lowercase
    return all(word and word[0].isupper() and word[1:].islower() for word in words)

