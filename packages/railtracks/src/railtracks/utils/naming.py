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
    if not snake_case_name:
        return ""
    
    # Split by underscores and capitalize each word
    words = snake_case_name.split('_')
    title_case_words = [word.capitalize() for word in words if word]
    return ' '.join(title_case_words)


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
    if not title_case_name:
        return ""
    
    # Split by spaces and join with underscores, then lowercase
    words = title_case_name.split()
    snake_case_words = [word.lower() for word in words if word]
    return '_'.join(snake_case_words)