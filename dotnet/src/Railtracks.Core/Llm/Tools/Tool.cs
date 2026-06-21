using System.Reflection;

namespace Railtracks.Llm.Tools;

using JsonObject = IReadOnlyDictionary<string, object?>;

/// <summary>
/// A quasi-immutable representation of a single tool: name, description, and parameters.
/// Ported from the Python <c>Tool</c>.
/// </summary>
public sealed class Tool
{
    public Tool(string name, string detail, IReadOnlyList<Parameter>? parameters = null)
    {
        Name = name;
        Detail = detail;
        Parameters = parameters;
    }

    /// <summary>
    /// Constructs a tool from a JSON-schema dictionary (with "properties"/"required"),
    /// matching the Python overload that accepts a schema dict.
    /// </summary>
    public Tool(string name, string detail, JsonObject schema)
    {
        Name = name;
        Detail = detail;

        if (schema.TryGetValue("properties", out var propsObj)
            && propsObj is IDictionary<string, object?> props && props.Count > 0)
        {
            var required = schema.TryGetValue("required", out var r) && r is IEnumerable<object?> reqs
                ? reqs.Select(x => x?.ToString() ?? string.Empty).ToHashSet()
                : new HashSet<string>();

            Parameters = props
                .Select(kv => SchemaParser.ParseJsonSchemaToParameter(
                    kv.Key,
                    kv.Value as JsonObject ?? new Dictionary<string, object?>(),
                    required.Contains(kv.Key)))
                .ToList();
        }
    }

    public string Name { get; }
    public string Detail { get; }
    public IReadOnlyList<Parameter>? Parameters { get; }

    public override string ToString()
    {
        var paramsStr = Parameters is { Count: > 0 }
            ? "{" + string.Join(", ", Parameters) + "}"
            : "None";
        return $"Tool(name={Name}, detail={Detail}, parameters={paramsStr})";
    }

    /// <summary>
    /// Creates a <see cref="Tool"/> from a method via reflection. The C# analog of the Python
    /// <c>from_function</c>: parameter types come from the signature, required-ness from the
    /// presence of a default value, and descriptions from the supplied <paramref name="argDescriptions"/>
    /// (C# has no runtime docstrings, so descriptions are provided explicitly).
    /// </summary>
    public static Tool FromMethod(
        MethodInfo method,
        string? name = null,
        string? details = null,
        IReadOnlyDictionary<string, string>? argDescriptions = null)
    {
        argDescriptions ??= new Dictionary<string, string>();
        var parameters = new List<Parameter>();

        foreach (var p in method.GetParameters())
        {
            var description = argDescriptions.TryGetValue(p.Name!, out var desc) ? desc : string.Empty;
            var required = !p.HasDefaultValue;
            parameters.Add(BuildParameter(p.Name!, p.ParameterType, description, required));
        }

        return new Tool(name ?? method.Name, details ?? string.Empty, parameters);
    }

    /// <summary>Convenience overload that builds a tool from a delegate's target method.</summary>
    public static Tool FromDelegate(Delegate func, string? name = null, string? details = null,
        IReadOnlyDictionary<string, string>? argDescriptions = null) =>
        FromMethod(func.Method, name, details, argDescriptions);

    private static Parameter BuildParameter(string name, Type type, string description, bool required)
    {
        // Optional<T> handling: Nullable<T> means the value may be absent.
        var underlying = Nullable.GetUnderlyingType(type);
        if (underlying is not null)
            return BuildParameter(name, underlying, description, false);

        // Sequence types -> ArrayParameter.
        if (type != typeof(string) && TryGetEnumerableElement(type, out var element))
        {
            var itemParam = IsComplexObject(element)
                ? BuildObjectParameter($"{name}_item", element, $"Item of type {element.Name}", true)
                : new Parameter($"{name}_item", description, true, paramType: element);
            return new ArrayParameter(name, itemParam, description, required);
        }

        // Complex object types -> ObjectParameter built from public properties.
        if (IsComplexObject(type))
            return BuildObjectParameter(name, type, description, required);

        // Primitives / fallback.
        return new Parameter(name, description, required, paramType: type);
    }

    private static ObjectParameter BuildObjectParameter(string name, Type type, string description, bool required)
    {
        var props = type.GetProperties(BindingFlags.Public | BindingFlags.Instance)
            .Select(prop =>
            {
                var propRequired = Nullable.GetUnderlyingType(prop.PropertyType) is null
                    && (prop.PropertyType.IsValueType || prop.PropertyType == typeof(string));
                return BuildParameter(prop.Name, prop.PropertyType, string.Empty, propRequired);
            })
            .ToList();

        return new ObjectParameter(name, props, description, required);
    }

    private static bool TryGetEnumerableElement(Type type, out Type element)
    {
        if (type.IsArray)
        {
            element = type.GetElementType()!;
            return true;
        }

        var enumerable = type.GetInterfaces()
            .Concat(new[] { type })
            .FirstOrDefault(i => i.IsGenericType && i.GetGenericTypeDefinition() == typeof(IEnumerable<>));
        if (enumerable is not null)
        {
            element = enumerable.GetGenericArguments()[0];
            return true;
        }

        element = typeof(object);
        return false;
    }

    private static bool IsComplexObject(Type type) =>
        type.IsClass && type != typeof(string) && !type.IsPrimitive;
}

/// <summary>Exception raised when a tool cannot be created. Ported from <c>ToolCreationError</c>.</summary>
public sealed class ToolCreationException : LlmException
{
    public ToolCreationException(string message, IReadOnlyList<string>? notes = null)
        : base(message)
    {
        Notes = notes ?? Array.Empty<string>();
    }

    public IReadOnlyList<string> Notes { get; }

    public override string ToString()
    {
        var baseMessage = Message;
        if (Notes.Count > 0)
        {
            var notesStr = "\n" + Color("Tips to debug:\n", Green)
                + string.Join("\n", Notes.Select(n => Color($"- {n}", Green)));
            return $"\n{Color(baseMessage, Red)}{notesStr}";
        }

        return Color(baseMessage, Red);
    }
}
