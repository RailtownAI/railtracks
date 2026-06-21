using FluentAssertions;
using Railtracks.Llm;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported from tests/unit_tests/llm/test_content.py
public class ToolCallTests
{
    [Fact]
    public void ToString_FormatsNameAndArguments()
    {
        var toolCall = new ToolCall("123", "example_tool",
            new Dictionary<string, object?> { ["arg1"] = "value1", ["arg2"] = "value2" });

        // Adapted from the Python dict-repr format to an idiomatic C# rendering.
        toolCall.ToString().Should().Be("example_tool({arg1=value1, arg2=value2})");
    }

    [Theory]
    [InlineData(null, "example_tool")]
    [InlineData("123", null)]
    public void Constructor_NullRequiredField_Throws(string? identifier, string? name)
    {
        var act = () => new ToolCall(identifier!, name!, new Dictionary<string, object?> { ["a"] = 1 });
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void Constructor_NullArguments_Throws()
    {
        var act = () => new ToolCall("123", "example_tool", null!);
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void Fixture_ExposesFields()
    {
        var call = new ToolCall("123", "example_tool", new Dictionary<string, object?> { ["arg1"] = "value1" });
        call.Identifier.Should().Be("123");
        call.Name.Should().Be("example_tool");
        call.Arguments.Should().ContainKey("arg1").WhoseValue.Should().Be("value1");
    }
}

public class ToolResponseTests
{
    [Fact]
    public void ToString_FormatsNameAndResult()
    {
        var response = new ToolResponse("123", "example_tool", "success");
        response.ToString().Should().Be("example_tool -> success");
    }

    [Theory]
    [InlineData(null, "example_tool", "success")]
    [InlineData("123", null, "success")]
    [InlineData("123", "example_tool", null)]
    public void Constructor_NullRequiredField_Throws(string? id, string? name, string? result)
    {
        var act = () => new ToolResponse(id!, name!, result!);
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void Fixture_ExposesFields()
    {
        var response = new ToolResponse("123", "example_tool", "success");
        response.Identifier.Should().Be("123");
        response.Name.Should().Be("example_tool");
        response.Result.Should().Be("success");
    }
}

public class StreamTests
{
    [Fact]
    public void Construction_SetsFinalMessage()
    {
        var stream = new Stream<string>(new[] { "chunk 1", "chunk 2" }, "Done");
        stream.FinalMessage.Should().Be("Done");
    }

    [Fact]
    public void Properties_ExposeStreamerAndFinalMessage()
    {
        var chunks = new[] { "chunk 1", "chunk 2" };
        var stream = new Stream<string>(chunks, "Final!");
        stream.Streamer.Should().BeSameAs(chunks);
        stream.FinalMessage.Should().Be("Final!");
    }

    [Fact]
    public void EmptyStreamer_YieldsNothing()
    {
        var stream = new Stream<string>(Array.Empty<string>(), string.Empty);
        stream.FinalMessage.Should().BeEmpty();
        stream.Streamer.Should().BeEmpty();
    }

    [Fact]
    public void NullStreamer_Throws()
    {
        var act = () => new Stream<string>(null!, "Done");
        act.Should().Throw<ArgumentException>();
    }
}
