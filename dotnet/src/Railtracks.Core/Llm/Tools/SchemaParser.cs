namespace Railtracks.Llm.Tools;

using JsonObject = IReadOnlyDictionary<string, object?>;

/// <summary>
/// Parses JSON-schema property dictionaries into <see cref="Parameter"/> instances.
/// Ported from the Python <c>schema_parser</c> module. Schema objects are represented as
/// <c>IReadOnlyDictionary&lt;string, object?&gt;</c> (matching a deserialized JSON object).
/// </summary>
public static class SchemaParser
{
    /// <summary>Parse a JSON-schema property dict into the appropriate <see cref="Parameter"/> subtype.</summary>
    public static Parameter ParseJsonSchemaToParameter(string name, JsonObject schema, bool required)
    {
        var paramType = ExtractParamType(schema);
        var description = GetString(schema, "description") ?? string.Empty;
        var @enum = GetList(schema, "enum");
        var defaultPresent = schema.ContainsKey("default");
        var @default = schema.TryGetValue("default", out var d) ? d : null;
        var additionalProperties = GetBool(schema, "additionalProperties");

        if (schema.ContainsKey("$ref"))
            return new RefParameter(name, (string)schema["$ref"]!, description, required);

        if (schema.ContainsKey("allOf"))
        {
            var (result, updatedType) = HandleAllOf(name, schema, required, description, additionalProperties);
            if (result is not null)
                return result;
            if (updatedType is not null)
                paramType = updatedType;
        }

        if (schema.ContainsKey("anyOf"))
            return HandleAnyOf(name, schema, required, description, @default, defaultPresent);

        if ((Equals(paramType, "object") || (paramType is List<string> l && l.Contains("object")))
            && schema.ContainsKey("properties"))
        {
            return HandleObject(name, schema, required, description, additionalProperties);
        }

        if (Equals(paramType, "array") && schema.ContainsKey("items"))
            return HandleArray(name, schema, required, description, @default, additionalProperties);

        if (paramType is List<string> types)
        {
            var options = types.Select(t => MapTokenToParameter(t)).ToList();
            return new UnionParameter(name, options, description, required, @default, @enum, defaultPresent);
        }

        return new Parameter(name, description, required, @default, @enum, defaultPresent, paramType);
    }

    /// <summary>Returns the top-level properties of a (pydantic-style) JSON schema as parameters.</summary>
    public static List<Parameter> ParseModelProperties(JsonObject schema)
    {
        var requiredFields = GetStringList(schema, "required");
        var nestedModels = ParseModelDefs(GetObject(schema, "$defs"));
        return ParseMainProperties(GetObject(schema, "properties"), requiredFields, nestedModels);
    }

    // ---- helpers ported from the Python module ----

    private static object ExtractParamType(JsonObject schema)
    {
        object? paramType = schema.TryGetValue("type", out var t) ? t : null;

        if (paramType is null)
        {
            if (schema.ContainsKey("properties")) return "object";
            if (schema.ContainsKey("items")) return "array";
            return "object";
        }

        if (paramType is IEnumerable<object?> list)
        {
            return list.Select(x => x as string == "null" ? "none" : (string)x!).ToList();
        }

        return paramType;
    }

    private static (Parameter?, object?) HandleAllOf(
        string name, JsonObject schema, bool required, string description, bool additionalProperties)
    {
        object? paramType = null;
        foreach (var itemObj in GetObjectList(schema, "allOf"))
        {
            if (itemObj.ContainsKey("$ref"))
            {
                return (new ObjectParameter(name, new List<Parameter>(), description, required, additionalProperties), null);
            }

            if (itemObj.TryGetValue("type", out var ty))
                paramType = ty;
        }

        return (null, paramType);
    }

    private static Parameter HandleAnyOf(
        string name, JsonObject schema, bool required, string description, object? @default, bool defaultPresent)
    {
        var options = new List<Parameter>();
        var idx = 0;
        foreach (var optionSchema in GetObjectList(schema, "anyOf"))
            options.Add(ParseJsonSchemaToParameter($"{name}_option_{idx++}", optionSchema, true));

        var flattened = new List<Parameter>();
        foreach (var opt in options)
        {
            if (opt is UnionParameter union)
                flattened.AddRange(union.Options);
            else
                flattened.Add(opt);
        }

        if (flattened.Count == 1)
            return flattened[0];

        return new UnionParameter(name, flattened, description, required, @default, null, defaultPresent);
    }

    private static ObjectParameter HandleObject(
        string name, JsonObject schema, bool required, string description, bool additionalProperties)
    {
        var innerRequired = GetStringList(schema, "required");
        var innerProps = GetObject(schema, "properties")
            .Select(kv => ParseJsonSchemaToParameter(kv.Key, AsObject(kv.Value), innerRequired.Contains(kv.Key)))
            .ToList();

        return new ObjectParameter(
            name,
            innerProps,
            string.IsNullOrEmpty(description) ? GetString(schema, "description") : description,
            required,
            GetBool(schema, "additionalProperties", additionalProperties),
            schema.TryGetValue("default", out var def) ? def : null);
    }

    private static ArrayParameter HandleArray(
        string name, JsonObject schema, bool required, string description, object? @default, bool additionalProperties)
    {
        var itemsSchema = AsObject(schema["items"]);
        var maxItems = schema.TryGetValue("maxItems", out var mi) && mi is not null ? Convert.ToInt32(mi) : (int?)null;

        Parameter itemParam;
        if (Equals(GetString(itemsSchema, "type"), "object") && itemsSchema.ContainsKey("properties"))
        {
            var innerRequired = GetStringList(itemsSchema, "required");
            itemParam = new ObjectParameter(
                $"{name}_item",
                GetObject(itemsSchema, "properties")
                    .Select(kv => ParseJsonSchemaToParameter(kv.Key, AsObject(kv.Value), innerRequired.Contains(kv.Key)))
                    .ToList(),
                GetString(itemsSchema, "description") ?? string.Empty,
                true,
                GetBool(itemsSchema, "additionalProperties"));
        }
        else
        {
            itemParam = new Parameter(
                $"{name}_item",
                GetString(itemsSchema, "description") ?? string.Empty,
                true,
                itemsSchema.TryGetValue("default", out var idef) ? idef : null,
                GetList(itemsSchema, "enum"),
                paramType: GetString(itemsSchema, "type") ?? "string");
        }

        return new ArrayParameter(name, itemParam, description, required, @default, maxItems, additionalProperties);
    }

    private static Dictionary<string, List<Parameter>> ParseModelDefs(JsonObject defs)
    {
        var result = new Dictionary<string, List<Parameter>>();
        foreach (var (defName, defSchemaObj) in defs)
        {
            var defSchema = AsObject(defSchemaObj);
            var nestedRequired = GetStringList(defSchema, "required");
            var nestedProps = GetObject(defSchema, "properties")
                .Select(kv => ParseJsonSchemaToParameter(kv.Key, AsObject(kv.Value), nestedRequired.Contains(kv.Key)))
                .ToList();
            result[defName] = nestedProps;
        }

        return result;
    }

    private static List<Parameter> ParseMainProperties(
        JsonObject properties, IReadOnlyCollection<string> requiredFields, IReadOnlyDictionary<string, List<Parameter>> nestedModels)
    {
        var result = new List<Parameter>();
        foreach (var (propName, propSchemaObj) in properties)
        {
            var propSchema = AsObject(propSchemaObj);

            if (propSchema.ContainsKey("$ref"))
            {
                var refObj = HandleRefProperty(propName, propSchema, requiredFields, nestedModels);
                if (refObj is not null) { result.Add(refObj); continue; }
            }

            if (propSchema.ContainsKey("allOf"))
            {
                var allOfObj = HandleAllOfProperty(propName, propSchema, requiredFields, nestedModels);
                if (allOfObj is not null) { result.Add(allOfObj); continue; }
            }

            var paramType = GetString(propSchema, "type") ?? "object";
            if (paramType == "object" && propSchema.ContainsKey("properties"))
                result.Add(HandleObjectProperty(propName, propSchema, requiredFields));
            else
                result.Add(ParseJsonSchemaToParameter(propName, propSchema, requiredFields.Contains(propName)));
        }

        return result;
    }

    private static ObjectParameter? HandleRefProperty(
        string propName, JsonObject propSchema, IReadOnlyCollection<string> requiredFields,
        IReadOnlyDictionary<string, List<Parameter>> nestedModels)
    {
        var refPath = (string)propSchema["$ref"]!;
        if (refPath.StartsWith("#/$defs/", StringComparison.Ordinal))
        {
            var modelName = refPath["#/$defs/".Length..];
            if (nestedModels.TryGetValue(modelName, out var props))
            {
                return new ObjectParameter(propName, props, GetString(propSchema, "description") ?? string.Empty,
                    requiredFields.Contains(propName));
            }
        }

        return null;
    }

    private static ObjectParameter? HandleAllOfProperty(
        string propName, JsonObject propSchema, IReadOnlyCollection<string> requiredFields,
        IReadOnlyDictionary<string, List<Parameter>> nestedModels)
    {
        foreach (var item in GetObjectList(propSchema, "allOf"))
        {
            if (item.ContainsKey("$ref"))
            {
                var refPath = (string)item["$ref"]!;
                if (refPath.StartsWith("#/$defs/", StringComparison.Ordinal))
                {
                    var modelName = refPath["#/$defs/".Length..];
                    if (nestedModels.TryGetValue(modelName, out var props))
                    {
                        return new ObjectParameter(propName, props, GetString(propSchema, "description") ?? string.Empty,
                            requiredFields.Contains(propName));
                    }
                }
            }
        }

        return null;
    }

    private static ObjectParameter HandleObjectProperty(
        string propName, JsonObject propSchema, IReadOnlyCollection<string> requiredFields)
    {
        var innerRequired = GetStringList(propSchema, "required");
        var innerProps = GetObject(propSchema, "properties")
            .Select(kv => ParseJsonSchemaToParameter(kv.Key, AsObject(kv.Value), innerRequired.Contains(kv.Key)))
            .ToList();

        return new ObjectParameter(propName, innerProps, GetString(propSchema, "description") ?? string.Empty,
            requiredFields.Contains(propName), GetBool(propSchema, "additionalProperties"));
    }

    // Replicates the Python `param_from_python_type` behavior for a schema-type token (only
    // "none" is a recognized key; anything else maps to object — matching from_python_type).
    private static Parameter MapTokenToParameter(string token)
    {
        var type = token == "none" ? ParameterType.None : ParameterType.Object;
        return new Parameter(string.Empty, paramType: type.Value());
    }

    // ---- dictionary access helpers ----

    private static JsonObject AsObject(object? value) =>
        value as JsonObject
        ?? (value is IDictionary<string, object?> d ? new Dictionary<string, object?>(d) : null)
        ?? new Dictionary<string, object?>();

    private static string? GetString(JsonObject schema, string key) =>
        schema.TryGetValue(key, out var v) ? v as string : null;

    private static bool GetBool(JsonObject schema, string key, bool fallback = false) =>
        schema.TryGetValue(key, out var v) && v is bool b ? b : fallback;

    private static IReadOnlyList<object?>? GetList(JsonObject schema, string key) =>
        schema.TryGetValue(key, out var v) && v is IEnumerable<object?> e ? e.ToList() : null;

    private static List<string> GetStringList(JsonObject schema, string key) =>
        schema.TryGetValue(key, out var v) && v is IEnumerable<object?> e
            ? e.Select(x => x?.ToString() ?? string.Empty).ToList()
            : new List<string>();

    private static JsonObject GetObject(JsonObject schema, string key) =>
        schema.TryGetValue(key, out var v) ? AsObject(v) : new Dictionary<string, object?>();

    private static IEnumerable<JsonObject> GetObjectList(JsonObject schema, string key) =>
        schema.TryGetValue(key, out var v) && v is IEnumerable<object?> e
            ? e.Select(AsObject)
            : Enumerable.Empty<JsonObject>();
}
