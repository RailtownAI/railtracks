namespace Railtracks.Llm;

/// <summary>
/// Supported LLM model providers. Ported from the Python <c>ModelProvider(str, Enum)</c>.
/// The string <see cref="ModelProviderExtensions.Value"/> matches the Python enum values
/// (some of which differ from the member name, e.g. Gemini -&gt; "Vertex_AI").
/// </summary>
public enum ModelProvider
{
    OpenAI,
    Anthropic,
    Gemini,
    HuggingFace,
    AzureAI,
    Ollama,
    Cohere,
    Telus,
    PortKey,
    Unknown,
}

public static class ModelProviderExtensions
{
    public static string Value(this ModelProvider provider) => provider switch
    {
        ModelProvider.OpenAI => "OpenAI",
        ModelProvider.Anthropic => "Anthropic",
        ModelProvider.Gemini => "Vertex_AI",
        ModelProvider.HuggingFace => "HuggingFace",
        ModelProvider.AzureAI => "AzureAI",
        ModelProvider.Ollama => "Ollama",
        ModelProvider.Cohere => "cohere_chat",
        ModelProvider.Telus => "Telus",
        ModelProvider.PortKey => "PortKey",
        ModelProvider.Unknown => "Unknown",
        _ => throw new ArgumentOutOfRangeException(nameof(provider), provider, null),
    };
}
