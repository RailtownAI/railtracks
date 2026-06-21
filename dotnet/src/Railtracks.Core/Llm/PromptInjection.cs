using System.Text.RegularExpressions;

namespace Railtracks.Llm;

/// <summary>
/// Minimal prompt-injection formatter. Ported from the Python <c>KeyOnlyFormatter</c>:
/// substitutes <c>{key}</c> placeholders from the provided values while leaving unknown
/// placeholders untouched (so partial fills don't raise).
/// </summary>
public static class PromptInjection
{
    private static readonly Regex Placeholder = new(@"\{(\w+)\}", RegexOptions.Compiled);

    public static string KeyOnlyFormat(string template, IReadOnlyDictionary<string, object?> values)
    {
        return Placeholder.Replace(template, match =>
        {
            var key = match.Groups[1].Value;
            return values.TryGetValue(key, out var value)
                ? value?.ToString() ?? string.Empty
                : match.Value; // leave unknown placeholders as-is
        });
    }
}
