using FluentAssertions;
using Railtracks.Llm.Tools;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported from tests/unit_tests/llm/tools/test_docstring_parser.py
public class DocstringParserTests
{
    [Fact]
    public void ExtractMainDescription_Empty()
    {
        DocstringParser.ExtractMainDescription("").Should().BeEmpty();
        DocstringParser.ExtractMainDescription(null).Should().BeEmpty();
    }

    [Fact]
    public void ExtractMainDescription_Simple()
    {
        DocstringParser.ExtractMainDescription("This is a simple description.")
            .Should().Be("This is a simple description.");
    }

    [Fact]
    public void ExtractMainDescription_StopsAtSections()
    {
        var docstring = """
            This is the main description.

            Args:
                param1: Description of param1.

            Returns:
                The return value.
            """;
        DocstringParser.ExtractMainDescription(docstring).Should().Be("This is the main description.");
    }

    [Fact]
    public void ExtractArgsSection_NoArgs_ReturnsEmpty()
    {
        DocstringParser.ExtractArgsSection("This is a docstring without an Args section.")
            .Should().BeEmpty();
    }

    [Fact]
    public void ExtractArgsSection_Simple()
    {
        var docstring = """
            This is a docstring.

            Args:
                param1: Description of param1.
                param2: Description of param2.

            Returns:
                The return value.
            """;
        var result = DocstringParser.ExtractArgsSection(docstring);
        result.Should().Contain("param1: Description of param1.");
        result.Should().Contain("param2: Description of param2.");
    }

    [Fact]
    public void ParseDocstringArgs_MapsNamesToDescriptions()
    {
        var docstring = """
            This is the main description.

            Args:
                param1: Description of param1.
                param2 (int): Description of param2.

            Returns:
                The return value.
            """;
        var result = DocstringParser.ParseDocstringArgs(docstring);
        result.Should().ContainKey("param1").WhoseValue.Should().Be("Description of param1.");
        result.Should().ContainKey("param2").WhoseValue.Should().Be("Description of param2.");
    }

    [Fact]
    public void ParseDocstringArgs_EmptyDocstring_ReturnsEmpty()
    {
        DocstringParser.ParseDocstringArgs("").Should().BeEmpty();
    }
}
