namespace Railtracks.Llm;

/// <summary>
/// A history of messages. Has all the capabilities of a <see cref="List{T}"/>
/// (Add, Remove, ...). Ported from the Python <c>MessageHistory(List[Message])</c>.
/// </summary>
public sealed class MessageHistory : List<Message>
{
    public MessageHistory() { }

    public MessageHistory(IEnumerable<Message> messages) : base(messages) { }

    /// <summary>Returns a new <see cref="MessageHistory"/> with all system messages removed.</summary>
    public MessageHistory RemovedSystemMessages() =>
        new(this.Where(m => m.Role != Role.System));

    public override string ToString() => string.Join("\n", this.Select(m => m.ToString()));
}
