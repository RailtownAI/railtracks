namespace Railtracks.Llm.Tools;

/// <summary>Parameter representing an array type. Ported from <c>ArrayParameter</c>.</summary>
public sealed class ArrayParameter : Parameter
{
    public ArrayParameter(
        string name,
        Parameter items,
        string? description = null,
        bool required = true,
        object? @default = null,
        int? maxItems = null,
        bool additionalProperties = false)
        : base(name, description, required, @default)
    {
        Items = items;
        MaxItems = maxItems;
        AdditionalProperties = additionalProperties;
        ParamType = ParameterType.Array.Value();
    }

    public Parameter Items { get; }
    public int? MaxItems { get; }
    public bool AdditionalProperties { get; }

    public override Dictionary<string, object?> ToJsonSchema()
    {
        var schema = new Dictionary<string, object?>
        {
            ["type"] = "array",
            ["items"] = Items.ToJsonSchema(),
        };

        if (!string.IsNullOrEmpty(Description))
            schema["description"] = Description;
        if (MaxItems is not null)
            schema["maxItems"] = MaxItems;
        if (Default is not null)
            schema["default"] = Default;
        if (Enum is { Count: > 0 })
            schema["enum"] = Enum;

        return schema;
    }

    public override string ToString() =>
        $"ArrayParameter(name='{Name}', items={Items}, description='{Description}', " +
        $"required={Required}, default={Default}, max_items={MaxItems}, " +
        $"additional_properties={AdditionalProperties})";
}
