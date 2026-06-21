using System.Text;
using System.Text.RegularExpressions;

namespace Railtracks.Llm.Tools;

/// <summary>
/// Utilities for parsing Google-style docstrings to extract parameter descriptions and
/// the main description. Ported from the Python <c>docstring_parser</c> module.
/// </summary>
public static class DocstringParser
{
    private static readonly Regex ArgPattern = new(
        @"^\s*(\w+)(?:\s*\([^)]+\))?:\s*(.+)$", RegexOptions.Compiled);

    /// <summary>Creates a <see cref="Parameter"/> from a CLR type. Ported from <c>param_from_python_type</c>.</summary>
    public static Parameter ParamFromClrType(Type? clrType, string name = "",
        string? description = null, bool required = true)
    {
        var mapped = ParameterTypeExtensions.FromClrType(clrType).Value();
        return new Parameter(name, description, required, paramType: mapped);
    }

    /// <summary>Parses the "Args:" section, mapping parameter names to descriptions.</summary>
    public static Dictionary<string, string> ParseDocstringArgs(string? docstring)
    {
        if (string.IsNullOrEmpty(docstring))
            return new Dictionary<string, string>();

        var argsSection = ExtractArgsSection(docstring);
        return string.IsNullOrEmpty(argsSection)
            ? new Dictionary<string, string>()
            : ParseArgsSection(argsSection);
    }

    /// <summary>Extracts the raw "Args:" section text from a docstring.</summary>
    public static string ExtractArgsSection(string? docstring)
    {
        if (string.IsNullOrEmpty(docstring))
            return string.Empty;

        var builder = new StringBuilder();
        var inArgs = false;
        foreach (var line in SplitLines(docstring))
        {
            if (line.Trim().StartsWith("Args:", StringComparison.Ordinal))
            {
                inArgs = true;
                continue;
            }

            if (inArgs)
            {
                var trimmed = line.Trim();
                if (trimmed.Length > 0 && trimmed.EndsWith(':') && !line.StartsWith(" ", StringComparison.Ordinal))
                    break;
                builder.Append(line).Append('\n');
            }
        }

        return builder.ToString();
    }

    /// <summary>Parses an "Args:" section into a parameter-name -&gt; description map.</summary>
    public static Dictionary<string, string> ParseArgsSection(string argsSection)
    {
        var result = new Dictionary<string, string>();
        string? currentArg = null;
        var currentDescription = new List<string>();

        foreach (var line in SplitLines(argsSection))
        {
            if (string.IsNullOrWhiteSpace(line))
                continue;

            var match = ArgPattern.Match(line);
            if (match.Success)
            {
                if (currentArg is not null && currentDescription.Count > 0)
                    result[currentArg] = string.Join(" ", currentDescription).Trim();

                currentArg = match.Groups[1].Value;
                currentDescription = new List<string> { match.Groups[2].Value.Trim() };
            }
            else if (currentArg is not null)
            {
                currentDescription.Add(line.Trim());
            }
        }

        if (currentArg is not null && currentDescription.Count > 0)
            result[currentArg] = string.Join(" ", currentDescription).Trim();

        return result;
    }

    /// <summary>Extracts the main description (everything before the first section marker).</summary>
    public static string ExtractMainDescription(string? docstring)
    {
        if (string.IsNullOrEmpty(docstring))
            return string.Empty;

        var lines = new List<string>();
        foreach (var line in SplitLines(docstring))
        {
            var trimmed = line.Trim();
            if (trimmed.Length > 0 && trimmed.EndsWith(':') && !line.StartsWith(" ", StringComparison.Ordinal))
                break;
            lines.Add(line);
        }

        return string.Join("\n", lines).Trim();
    }

    private static IEnumerable<string> SplitLines(string text) =>
        text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
}
