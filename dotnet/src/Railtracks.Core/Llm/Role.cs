namespace Railtracks.Llm;

/// <summary>
/// Represents the role of a message. Ported from the Python <c>Role(str, Enum)</c>.
/// </summary>
public enum Role
{
    Assistant,
    User,
    System,
    Tool,
}

/// <summary>
/// Helpers for mapping <see cref="Role"/> to/from its wire string value
/// (e.g. <c>Role.Assistant</c> &lt;-&gt; <c>"assistant"</c>).
/// </summary>
public static class RoleExtensions
{
    /// <summary>The lowercase string value of the role (matches the Python enum value).</summary>
    public static string Value(this Role role) => role switch
    {
        Role.Assistant => "assistant",
        Role.User => "user",
        Role.System => "system",
        Role.Tool => "tool",
        _ => throw new ArgumentOutOfRangeException(nameof(role), role, null),
    };

    public static Role FromValue(string value) => value switch
    {
        "assistant" => Role.Assistant,
        "user" => Role.User,
        "system" => Role.System,
        "tool" => Role.Tool,
        _ => throw new ArgumentException($"Unknown role: {value}", nameof(value)),
    };
}
