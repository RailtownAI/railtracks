namespace Railtracks.Llm.Tools;

/// <summary>Parameter representing a JSON-schema reference. Ported from <c>RefParameter</c>.</summary>
public sealed class RefParameter : Parameter
{
    public RefParameter(
        string name,
        string refPath,
        string? description = null,
        bool required = true,
        object? @default = null)
        : base(name, description, required, @default)
    {
        RefPath = refPath;
        ParamType = "object"; // referenced schemas are always object type
    }

    public string RefPath { get; }

    public override Dictionary<string, object?> ToJsonSchema()
    {
        var schema = new Dictionary<string, object?> { ["$ref"] = RefPath };

        if (!string.IsNullOrEmpty(Description))
            schema["description"] = Description;
        if (Default is not null)
            schema["default"] = Default;
        if (Enum is { Count: > 0 })
            schema["enum"] = Enum;

        return schema;
    }

    public override string ToString() =>
        $"RefParameter(name='{Name}', ref_path='{RefPath}', description='{Description}', " +
        $"required={Required}, default={Default})";
}
