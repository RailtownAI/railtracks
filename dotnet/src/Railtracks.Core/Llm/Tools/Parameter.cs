namespace Railtracks.Llm.Tools;

/// <summary>JSON-schema parameter types. Ported from the Python <c>ParameterType(str, Enum)</c>.</summary>
public enum ParameterType
{
    String,
    Integer,
    Float,
    Boolean,
    Array,
    Object,
    None,
}

public static class ParameterTypeExtensions
{
    /// <summary>The JSON-schema string value (matches the Python enum value).</summary>
    public static string Value(this ParameterType type) => type switch
    {
        ParameterType.String => "string",
        ParameterType.Integer => "integer",
        ParameterType.Float => "number",
        ParameterType.Boolean => "boolean",
        ParameterType.Array => "array",
        ParameterType.Object => "object",
        ParameterType.None => "null",
        _ => throw new ArgumentOutOfRangeException(nameof(type), type, null),
    };

    /// <summary>Maps a CLR type to a <see cref="ParameterType"/>. Ported from <c>from_python_type</c>.</summary>
    public static ParameterType FromClrType(Type? clrType)
    {
        if (clrType is null) return ParameterType.Object;
        var t = Nullable.GetUnderlyingType(clrType) ?? clrType;

        if (t == typeof(string)) return ParameterType.String;
        if (t == typeof(int) || t == typeof(long) || t == typeof(short) || t == typeof(byte))
            return ParameterType.Integer;
        if (t == typeof(float) || t == typeof(double) || t == typeof(decimal))
            return ParameterType.Float;
        if (t == typeof(bool)) return ParameterType.Boolean;
        // Dictionaries are IEnumerable but map to object (matching Python's dict -> OBJECT).
        if (typeof(System.Collections.IDictionary).IsAssignableFrom(t)
            || (t.IsGenericType && t.GetGenericTypeDefinition() == typeof(IDictionary<,>)))
            return ParameterType.Object;
        if (typeof(System.Collections.IEnumerable).IsAssignableFrom(t) && t != typeof(string))
            return ParameterType.Array;
        return ParameterType.Object;
    }
}

/// <summary>
/// Base parameter with default simple-parameter behavior. Ported from the Python
/// <c>Parameter</c> ABC (which is directly instantiable since it has no abstract members).
/// </summary>
public class Parameter
{
    public Parameter(
        string name,
        string? description = null,
        bool required = true,
        object? @default = null,
        IReadOnlyList<object?>? @enum = null,
        bool defaultPresent = false,
        object? paramType = null)
    {
        Name = name;
        Description = description ?? string.Empty;
        Required = required;
        Default = @default;
        Enum = @enum;
        DefaultPresent = defaultPresent;

        if (paramType is not null)
        {
            ParamType = paramType is System.Collections.IEnumerable list and not string
                ? list.Cast<object>().Select(NormalizeScalar).ToList()
                : NormalizeScalar(paramType);
        }
    }

    public string Name { get; }
    public string Description { get; set; }
    public bool Required { get; set; }
    public object? Default { get; set; }
    public IReadOnlyList<object?>? Enum { get; set; }
    public bool DefaultPresent { get; set; }

    /// <summary>The schema type: a <see cref="string"/>, a <c>List&lt;string&gt;</c> (union), or null.</summary>
    public object? ParamType { get; protected set; }

    /// <summary>Maps a ParameterType enum, schema string, or CLR type to a schema type string.</summary>
    protected static string NormalizeScalar(object paramType) => paramType switch
    {
        ParameterType pt => pt.Value(),
        Type clr => ParameterTypeExtensions.FromClrType(clr).Value(),
        string s => s,
        _ => paramType.ToString() ?? "object",
    };

    public virtual Dictionary<string, object?> ToJsonSchema()
    {
        var schema = new Dictionary<string, object?>
        {
            ["type"] = ParamType,
        };

        if (!string.IsNullOrEmpty(Description))
            schema["description"] = Description;

        if (Enum is { Count: > 0 })
            schema["enum"] = Enum;

        if (DefaultPresent)
            schema["default"] = Default;
        else if (ParamType is List<string> types && types.Contains("none"))
            schema["default"] = null;

        return schema;
    }

    public override string ToString() =>
        $"Parameter(name='{Name}', param_type={ParamType}, description='{Description}', " +
        $"required={Required}, default={Default}, enum={Enum})";
}
