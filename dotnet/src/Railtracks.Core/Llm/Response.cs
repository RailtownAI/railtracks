using System.Globalization;

namespace Railtracks.Llm;

/// <summary>
/// Additional information about a model response. Ported from the Python <c>MessageInfo</c>.
/// </summary>
public sealed class MessageInfo
{
    public MessageInfo(
        int? inputTokens = null,
        int? outputTokens = null,
        double? latency = null,
        string? modelName = null,
        double? totalCost = null,
        string? systemFingerprint = null)
    {
        InputTokens = inputTokens;
        OutputTokens = outputTokens;
        Latency = latency;
        ModelName = modelName;
        TotalCost = totalCost;
        SystemFingerprint = systemFingerprint;
    }

    public int? InputTokens { get; }
    public int? OutputTokens { get; }
    public double? Latency { get; }
    public string? ModelName { get; }
    public double? TotalCost { get; }
    public string? SystemFingerprint { get; }

    /// <summary>The total tokens used, or null if either input or output token count is missing.</summary>
    public int? TotalTokens =>
        InputTokens is null || OutputTokens is null ? null : InputTokens + OutputTokens;

    public override string ToString()
    {
        // Mirror the Python repr formatting so downstream string assertions hold.
        string Repr(double? d) => d?.ToString(CultureInfo.InvariantCulture) ?? "None";
        string ReprInt(int? i) => i?.ToString(CultureInfo.InvariantCulture) ?? "None";
        string ReprStr(string? s) => s is null ? "None" : $"'{s}'";

        return $"MessageInfo(input_tokens={ReprInt(InputTokens)}, " +
               $"output_tokens={ReprInt(OutputTokens)}, " +
               $"latency={Repr(Latency)}, " +
               $"model_name={ReprStr(ModelName)}, " +
               $"total_cost={Repr(TotalCost)}, " +
               $"system_fingerprint={ReprStr(SystemFingerprint)})";
    }
}

/// <summary>
/// A response from a model: the returned message plus metadata. Ported from <c>Response</c>.
/// </summary>
public sealed class Response
{
    public Response(Message message, MessageInfo? messageInfo = null)
    {
        // Python guards `isinstance(message, Message)`; the C# type system enforces this,
        // but we still reject null to preserve the "must be a Message" contract.
        Message = message ?? throw new ArgumentException("message must be of type Message, got null.");
        MessageInfo = messageInfo ?? new MessageInfo();
    }

    /// <summary>The message returned as part of this response.</summary>
    public Message Message { get; }

    /// <summary>Additional information about the message (tokens, latency, ...).</summary>
    public MessageInfo MessageInfo { get; }

    public override string ToString() => Message is not null ? Message.ToString() : "Response(<no-data>)";

    public string ToRepr() => $"Response(message={Message}, message_info={MessageInfo})";
}
