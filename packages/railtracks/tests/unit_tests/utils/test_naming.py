"""
Tests for the naming utilities.
"""

import pytest
from railtracks.utils.naming import snake_case_to_title_case, title_case_to_snake_case


class TestSnakeCaseToTitleCase:
    """Test converting snake_case to Title Case."""
    
    def test_simple_word(self):
        """Test converting a single word."""
        assert snake_case_to_title_case("simple") == "Simple"
    
    def test_two_words(self):
        """Test converting two words."""
        assert snake_case_to_title_case("test_function") == "Test Function"
    
    def test_multiple_words(self):
        """Test converting multiple words."""
        assert snake_case_to_title_case("number_of_chars") == "Number Of Chars"
        assert snake_case_to_title_case("calculate_sum_total") == "Calculate Sum Total"
    
    def test_empty_string(self):
        """Test empty string."""
        assert snake_case_to_title_case("") == ""
    
    def test_single_letter(self):
        """Test single letter."""
        assert snake_case_to_title_case("a") == "A"
    
    def test_multiple_underscores(self):
        """Test handling multiple consecutive underscores."""
        assert snake_case_to_title_case("test__function") == "Test Function"
        assert snake_case_to_title_case("test___function") == "Test Function"
    
    def test_leading_trailing_underscores(self):
        """Test handling leading and trailing underscores."""
        assert snake_case_to_title_case("_test_function_") == "Test Function"
        assert snake_case_to_title_case("__test__") == "Test"


class TestTitleCaseToSnakeCase:
    """Test converting Title Case to snake_case."""
    
    def test_simple_word(self):
        """Test converting a single word."""
        assert title_case_to_snake_case("Simple") == "simple"
    
    def test_two_words(self):
        """Test converting two words."""
        assert title_case_to_snake_case("Test Function") == "test_function"
    
    def test_multiple_words(self):
        """Test converting multiple words."""
        assert title_case_to_snake_case("Number Of Chars") == "number_of_chars"
        assert title_case_to_snake_case("Calculate Sum Total") == "calculate_sum_total"
    
    def test_empty_string(self):
        """Test empty string."""
        assert title_case_to_snake_case("") == ""
    
    def test_single_letter(self):
        """Test single letter."""
        assert title_case_to_snake_case("A") == "a"
    
    def test_multiple_spaces(self):
        """Test handling multiple consecutive spaces."""
        assert title_case_to_snake_case("Test  Function") == "test_function"
        assert title_case_to_snake_case("Test   Function") == "test_function"
    
    def test_leading_trailing_spaces(self):
        """Test handling leading and trailing spaces."""
        assert title_case_to_snake_case(" Test Function ") == "test_function"
        assert title_case_to_snake_case("  Test  ") == "test"


class TestRoundTripConversion:
    """Test that conversions are reversible where expected."""
    
    def test_snake_to_title_to_snake(self):
        """Test snake_case -> Title Case -> snake_case."""
        original = "test_function_name"
        title = snake_case_to_title_case(original)
        back_to_snake = title_case_to_snake_case(title)
        assert back_to_snake == original
    
    def test_title_to_snake_to_title(self):
        """Test Title Case -> snake_case -> Title Case."""
        original = "Test Function Name"
        snake = title_case_to_snake_case(original)
        back_to_title = snake_case_to_title_case(snake)
        assert back_to_title == original