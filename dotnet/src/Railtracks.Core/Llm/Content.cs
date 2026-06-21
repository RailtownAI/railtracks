namespace Railtracks.Llm;

/// <summary>
/// Represents the moment a tool is called. Ported from the Python pydantic <c>ToolCall</c>.
/// </summary>
public sealed class ToolCall
{
    public ToolCall(string identifier, string name, IReadOnlyDictionary<string, object?> arguments)
    {
        // pydantic raises ValidationError (a ValueError) when a required field is None.
        // The idiomatic C# analog is ArgumentNullException (an ArgumentException).
        Identifier = identifier ?? throw new ArgumentNullException(nameof(identifier));
        Name = name ?? throw new ArgumentNullException(nameof(name));
        Arguments = arguments ?? throw new ArgumentNullException(nameof(arguments));
    }

    /// <summary>The identifier attached to this tool call.</summary>
    public string Identifier { get; }

    /// <summary>The name of the tool being called.</summary>
    public string Name { get; }

    /// <summary>The arguments provided as input to the tool.</summary>
    public IReadOnlyDictionary<string, object?> Arguments { get; }

    public override string ToString()
    {
        var args = string.Join(", ", Arguments.Select(kv => $"{kv.Key}={kv.Value}"));
        return $"{Name}({{{args}}})";
    }
}

/// <summary>
/// Represents a tool response. Ported from the Python pydantic <c>ToolResponse</c>.
/// </summary>
public sealed class ToolResponse
{
    public ToolResponse(string identifier, string name, string result)
    {
        Identifier = identifier ?? throw new ArgumentNullException(nameof(identifier));
        Name = name ?? throw new ArgumentNullException(nameof(name));
        Result = result ?? throw new ArgumentNullException(nameof(result));
    }

    /// <summary>The identifier attached to this tool response (matches the tool call's identifier).</summary>
    public string Identifier { get; }

    /// <summary>The name of the tool that generated this response.</summary>
    public string Name { get; }

    /// <summary>The result of the tool call.</summary>
    public string Result { get; }

    public override string ToString() => $"{Name} -> {Result}";
}

/// <summary>
/// Represents a streaming response from a model. Ported from the Python <c>Stream</c>.
/// The Python generator becomes an <see cref="IEnumerable{T}"/> of chunk strings.
/// </summary>
/// <typeparam name="TOutput">The type of the final aggregated message (string or a structured model).</typeparam>
public sealed class Stream<TOutput>
{
    public Stream(IEnumerable<string> streamer, TOutput? finalMessage = default)
    {
        Streamer = streamer ?? throw new ArgumentNullException(
            nameof(streamer), "streamer must be a sequence of chunks.");
        FinalMessage = finalMessage;
    }

    /// <summary>The streamer that yields response chunks.</summary>
    public IEnumerable<string> Streamer { get; }

    /// <summary>The final message constructed once the streamer has finished.</summary>
    public TOutput? FinalMessage { get; set; }

    public override string ToString() => $"Stream(streamer={Streamer})";
}
