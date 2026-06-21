namespace Railtracks.Llm.Tools;

/// <summary>Parameter representing an object type. Ported from <c>ObjectParameter</c>.</summary>
public sealed class ObjectParameter : Parameter
{
    public ObjectParameter(
        string name,
        IReadOnlyList<Parameter> properties,
        string? description = null,
        bool required = true,
        bool additionalProperties = false,
        object? @default = null)
        : base(name, description, required, @default)
    {
        Properties = properties;
        AdditionalProperties = additionalProperties;
        ParamType = ParameterType.Object.Value();
    }

    public IReadOnlyList<Parameter> Properties { get; }
    public bool AdditionalProperties { get; }

    public override Dictionary<string, object?> ToJsonSchema()
    {
        var properties = new Dictionary<string, object?>();
        var requiredProps = new List<string>();

        foreach (var prop in Properties)
        {
            properties[prop.Name] = prop.ToJsonSchema();
            if (prop.Required)
                requiredProps.Add(prop.Name);
        }

        var schema = new Dictionary<string, object?>
        {
            ["type"] = "object",
            ["properties"] = properties,
            ["additionalProperties"] = AdditionalProperties,
        };

        if (!string.IsNullOrEmpty(Description))
            schema["description"] = Description;
        if (requiredProps.Count > 0)
            schema["required"] = requiredProps;
        if (Default is not null)
            schema["default"] = Default;
        if (Enum is { Count: > 0 })
            schema["enum"] = Enum;

        return schema;
    }

    public override string ToString() =>
        $"ObjectParameter(name='{Name}', properties=[{string.Join(", ", Properties)}], " +
        $"description='{Description}', required={Required}, " +
        $"additional_properties={AdditionalProperties}, default={Default})";
}
