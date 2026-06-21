namespace Railtracks.Llm.Tools;

/// <summary>Parameter representing a union type. Ported from <c>UnionParameter</c>.</summary>
public sealed class UnionParameter : Parameter
{
    public UnionParameter(
        string name,
        IReadOnlyList<Parameter> options,
        string? description = null,
        bool required = true,
        object? @default = null,
        IReadOnlyList<object?>? @enum = null,
        bool defaultPresent = false)
        : base(name, description, required, @default, @enum, defaultPresent)
    {
        Options = options;

        foreach (var opt in options)
        {
            if (opt is UnionParameter)
                throw new ArgumentException("UnionParameter cannot contain another UnionParameter in its options");
        }

        // param_type is the deduplicated set of inner option types.
        var flattened = new List<string>();
        foreach (var opt in options)
        {
            switch (opt.ParamType)
            {
                case List<string> list:
                    flattened.AddRange(list);
                    break;
                case string s:
                    flattened.Add(s);
                    break;
            }
        }

        ParamType = flattened.Distinct().ToList();
    }

    public IReadOnlyList<Parameter> Options { get; }

    public override Dictionary<string, object?> ToJsonSchema()
    {
        var schema = new Dictionary<string, object?>
        {
            ["anyOf"] = Options.Select(o => o.ToJsonSchema()).ToList(),
        };

        if (!string.IsNullOrEmpty(Description))
            schema["description"] = Description;
        if (DefaultPresent)
            schema["default"] = Default;

        return schema;
    }

    public override string ToString() =>
        $"UnionParameter(name='{Name}', options=[{string.Join(", ", Options)}], " +
        $"description='{Description}', required={Required}, default={Default})";
}
