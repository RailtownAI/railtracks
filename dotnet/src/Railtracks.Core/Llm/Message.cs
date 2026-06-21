namespace Railtracks.Llm;

/// <summary>
/// Base class for a message an LLM can read. Ported from the Python generic <c>Message</c>.
/// The content is held as <see cref="object"/> since it may be a string, a list of
/// <see cref="ToolCall"/>, a <see cref="ToolResponse"/>, or a structured model.
/// </summary>
public class Message
{
    public Message(object content, Role role, bool injectPrompt = true)
    {
        ValidateContent(content);
        Content = content;
        Role = role;
        InjectPrompt = injectPrompt;
    }

    /// <summary>Override to validate the content type for a specific message subtype.</summary>
    protected virtual void ValidateContent(object content) { }

    /// <summary>The content of the message.</summary>
    public object Content { get; protected set; }

    /// <summary>The role of the message.</summary>
    public Role Role { get; }

    /// <summary>Whether this message should have context variables injected into it.</summary>
    public bool InjectPrompt { get; set; }

    /// <summary>The tool calls attached to this message, if any; otherwise an empty list.</summary>
    public IReadOnlyList<ToolCall> ToolCalls =>
        Content is IEnumerable<ToolCall> calls ? calls.ToList() : new List<ToolCall>();

    public override string ToString() => $"{Role.Value()}: {Content}";
}

/// <summary>Base for messages that only accept string content. Ported from <c>_StringOnlyContent</c>.</summary>
public abstract class StringOnlyMessage : Message
{
    protected StringOnlyMessage(string content, Role role, bool injectPrompt = true)
        : base(content, role, injectPrompt) { }

    protected override void ValidateContent(object content)
    {
        if (content is not string)
            throw new ArgumentException($"A {GetType().Name} needs a string but got {content?.GetType()}.");
    }

    /// <summary>The string content of this message.</summary>
    public string Text => (string)Content;

    /// <summary>Injects context variables into the content, replacing <c>{key}</c> placeholders.</summary>
    public void FillPrompt(IReadOnlyDictionary<string, object?> values)
    {
        Content = PromptInjection.KeyOnlyFormat((string)Content, values);
    }
}

/// <summary>A user message. Only string content is supported. Ported from <c>UserMessage</c>.</summary>
public sealed class UserMessage : StringOnlyMessage
{
    public UserMessage(
        string? content = null,
        IReadOnlyList<string>? attachments = null,
        bool injectPrompt = true,
        bool trustUrls = false,
        double attachmentTimeout = 10.0)
        : base(NormalizeContent(content, attachments), Role.User, injectPrompt)
    {
        if (attachments is not null)
        {
            Attachment = attachments
                .Select(a => new Attachment(a, trustUrls, attachmentTimeout))
                .ToList();
        }
    }

    /// <summary>Convenience constructor for a single attachment.</summary>
    public UserMessage(string content, string attachment, bool injectPrompt = true,
        bool trustUrls = false, double attachmentTimeout = 10.0)
        : this(content, new[] { attachment }, injectPrompt, trustUrls, attachmentTimeout) { }

    /// <summary>The file attachment(s) for this message, or null if none.</summary>
    public IReadOnlyList<Attachment>? Attachment { get; }

    private static string NormalizeContent(string? content, IReadOnlyList<string>? attachments)
    {
        if (attachments is not null)
            return content ?? string.Empty;
        if (content is null)
            throw new ArgumentException("UserMessage must have content if no attachment is provided.");
        return content;
    }
}

/// <summary>A system message. Ported from <c>SystemMessage</c>.</summary>
public sealed class SystemMessage : StringOnlyMessage
{
    public SystemMessage(string content, bool injectPrompt = true)
        : base(content ?? throw new ArgumentException("A SystemMessage needs a string but got null."),
               Role.System, injectPrompt) { }
}

/// <summary>A message from the assistant. Ported from <c>AssistantMessage</c>.</summary>
public sealed class AssistantMessage : Message
{
    public AssistantMessage(object content, bool injectPrompt = true)
        : base(content, Role.Assistant, injectPrompt) { }

    /// <summary>
    /// Optionally stores the raw provider message so providers that attach extra metadata
    /// (e.g. Gemini thought_signature) can round-trip it back. Ported from <c>raw_litellm_message</c>.
    /// </summary>
    public object? RawProviderMessage { get; set; }
}

/// <summary>A message that is a tool call answer. Ported from <c>ToolMessage</c>.</summary>
public sealed class ToolMessage : Message
{
    public ToolMessage(ToolResponse content) : base(content, Role.Tool) { }

    protected override void ValidateContent(object content)
    {
        if (content is not ToolResponse)
        {
            throw new ArgumentException(
                $"A {GetType().Name} needs a ToolResponse but got {content?.GetType()}.");
        }
    }

    /// <summary>The tool response content.</summary>
    public ToolResponse Response => (ToolResponse)Content;
}
