using FluentAssertions;
using Railtracks.Llm.Tools;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported from tests/unit_tests/llm/tools/test_schema_parser.py
public class ParseJsonSchemaToParameterTests
{
    private static Dictionary<string, object?> Obj(params (string Key, object? Value)[] entries) =>
        entries.ToDictionary(e => e.Key, e => e.Value);

    [Fact]
    public void BasicStringParameter()
    {
        var schema = Obj(("type", "string"), ("description", "A string parameter"));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.Name.Should().Be("test_param");
        param.ParamType.Should().Be("string");
        param.Description.Should().Be("A string parameter");
        param.Required.Should().BeTrue();
    }

    [Fact]
    public void BasicIntegerParameter_NotRequired()
    {
        var schema = Obj(("type", "integer"), ("description", "An integer parameter"));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, false);
        param.ParamType.Should().Be("integer");
        param.Required.Should().BeFalse();
    }

    [Fact]
    public void NumberParameter_StaysNumber()
    {
        var schema = Obj(("type", "number"), ("description", "A number parameter"));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.ParamType.Should().Be("number");
    }

    [Fact]
    public void BooleanParameter()
    {
        var schema = Obj(("type", "boolean"), ("description", "A boolean parameter"));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.ParamType.Should().Be("boolean");
    }

    [Fact]
    public void ArrayParameter_PrimitiveItems()
    {
        var schema = Obj(
            ("type", "array"),
            ("description", "An array parameter"),
            ("items", Obj(("type", "string"))));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.ParamType.Should().Be("array");
        param.Description.Should().Be("An array parameter");
    }

    [Fact]
    public void ArrayParameter_ObjectItems()
    {
        var schema = Obj(
            ("type", "array"),
            ("description", "An array of objects"),
            ("items", Obj(
                ("type", "object"),
                ("properties", Obj(
                    ("name", Obj(("type", "string"), ("description", "The name"))),
                    ("age", Obj(("type", "integer"), ("description", "The age"))))),
                ("required", new List<string> { "name" }))));

        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.Should().BeOfType<ArrayParameter>();
        var items = ((ArrayParameter)param).Items;
        items.Should().BeOfType<ObjectParameter>();

        foreach (var prop in ((ObjectParameter)items).Properties)
        {
            if (prop.Name == "name") { prop.ParamType.Should().Be("string"); prop.Required.Should().BeTrue(); }
            else if (prop.Name == "age") { prop.ParamType.Should().Be("integer"); prop.Required.Should().BeFalse(); }
            else throw new Xunit.Sdk.XunitException($"Unexpected property: {prop.Name}");
        }
    }

    [Fact]
    public void ObjectParameter_WithRequired()
    {
        var schema = Obj(
            ("type", "object"),
            ("description", "An object parameter"),
            ("properties", Obj(
                ("name", Obj(("type", "string"))),
                ("age", Obj(("type", "integer"))))),
            ("required", new List<string> { "name" }));

        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.Should().BeOfType<ObjectParameter>();
        param.ParamType.Should().Be("object");

        foreach (var prop in ((ObjectParameter)param).Properties)
        {
            if (prop.Name == "name") prop.Required.Should().BeTrue();
            else if (prop.Name == "age") prop.Required.Should().BeFalse();
        }
    }

    [Fact]
    public void NestedObjectParameter()
    {
        var schema = Obj(
            ("type", "object"),
            ("properties", Obj(
                ("person", Obj(
                    ("type", "object"),
                    ("properties", Obj(
                        ("name", Obj(("type", "string"))),
                        ("address", Obj(
                            ("type", "object"),
                            ("properties", Obj(
                                ("street", Obj(("type", "string"))),
                                ("city", Obj(("type", "string"))))),
                            ("required", new List<string> { "street" }))))),
                    ("required", new List<string> { "name" }))))),
            ("required", new List<string> { "person" }));

        var param = (ObjectParameter)SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        var person = param.Properties.Single(p => p.Name == "person");
        person.Required.Should().BeTrue();
        person.ParamType.Should().Be("object");

        var address = ((ObjectParameter)person).Properties.Single(p => p.Name == "address");
        address.ParamType.Should().Be("object");

        var addressProps = ((ObjectParameter)address).Properties;
        addressProps.Single(p => p.Name == "street").Required.Should().BeTrue();
        addressProps.Single(p => p.Name == "city").Required.Should().BeFalse();
    }

    [Fact]
    public void RefParameter()
    {
        var schema = Obj(
            ("$ref", "#/components/schemas/Person"),
            ("description", "A reference to Person schema"));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.Should().BeOfType<RefParameter>();
        param.ParamType.Should().Be("object");
        param.Description.Should().Be("A reference to Person schema");
    }

    [Fact]
    public void DefaultTypeIsObject()
    {
        var schema = Obj(("description", "A parameter without type"));
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", schema, true);
        param.ParamType.Should().Be("object");
        param.Description.Should().Be("A parameter without type");
    }

    [Fact]
    public void EmptySchema_DefaultsToObject()
    {
        var param = SchemaParser.ParseJsonSchemaToParameter("test_param", new Dictionary<string, object?>(), true);
        param.ParamType.Should().Be("object");
        param.Description.Should().BeEmpty();
    }
}

public class ParseModelPropertiesTests
{
    private static Dictionary<string, object?> Obj(params (string Key, object? Value)[] entries) =>
        entries.ToDictionary(e => e.Key, e => e.Value);

    [Fact]
    public void SimpleSchema()
    {
        var schema = Obj(
            ("properties", Obj(
                ("name", Obj(("type", "string"))),
                ("age", Obj(("type", "integer"))),
                ("is_active", Obj(("type", "boolean"))))),
            ("required", new List<string> { "name", "age" }));

        var result = SchemaParser.ParseModelProperties(schema).ToDictionary(p => p.Name);
        result.Should().HaveCount(3);
        result["name"].ParamType.Should().Be("string");
        result["age"].ParamType.Should().Be("integer");
        result["is_active"].ParamType.Should().Be("boolean");
        result["name"].Required.Should().BeTrue();
        result["age"].Required.Should().BeTrue();
        result["is_active"].Required.Should().BeFalse();
    }

    [Fact]
    public void SchemaWithNestedObject()
    {
        var schema = Obj(
            ("properties", Obj(
                ("name", Obj(("type", "string"))),
                ("address", Obj(
                    ("type", "object"),
                    ("properties", Obj(
                        ("street", Obj(("type", "string"))),
                        ("city", Obj(("type", "string"))))),
                    ("required", new List<string> { "street" }))))),
            ("required", new List<string> { "name" }));

        var result = SchemaParser.ParseModelProperties(schema).ToDictionary(p => p.Name);
        result["address"].Should().BeOfType<ObjectParameter>();
        var addressProps = ((ObjectParameter)result["address"]).Properties;
        addressProps.Single(p => p.Name == "street").Required.Should().BeTrue();
        addressProps.Single(p => p.Name == "city").Required.Should().BeFalse();
    }

    [Fact]
    public void SchemaWithDefsAndRefs()
    {
        var schema = Obj(
            ("$defs", Obj(
                ("Address", Obj(
                    ("properties", Obj(
                        ("street", Obj(("type", "string"))),
                        ("city", Obj(("type", "string"))))),
                    ("required", new List<string> { "street" }))))),
            ("properties", Obj(
                ("name", Obj(("type", "string"))),
                ("address", Obj(("$ref", "#/$defs/Address"), ("description", "The address"))))),
            ("required", new List<string> { "name" }));

        var result = SchemaParser.ParseModelProperties(schema).ToDictionary(p => p.Name);
        result["address"].Should().BeOfType<ObjectParameter>();
        var addressProps = ((ObjectParameter)result["address"]).Properties.ToDictionary(p => p.Name);
        addressProps.Should().ContainKeys("street", "city");
        addressProps["street"].Required.Should().BeTrue();
        addressProps["city"].Required.Should().BeFalse();
    }

    [Fact]
    public void SchemaWithAllOfAndRefs()
    {
        var schema = Obj(
            ("$defs", Obj(
                ("Person", Obj(
                    ("properties", Obj(
                        ("name", Obj(("type", "string"))),
                        ("age", Obj(("type", "integer"))))),
                    ("required", new List<string> { "name" }))))),
            ("properties", Obj(
                ("user", Obj(
                    ("allOf", new List<object?>
                    {
                        Obj(("$ref", "#/$defs/Person")),
                        Obj(("type", "object"), ("description", "Additional user properties")),
                    }),
                    ("description", "The user"))))),
            ("required", new List<string> { "user" }));

        var result = SchemaParser.ParseModelProperties(schema).ToDictionary(p => p.Name);
        result["user"].Should().BeOfType<ObjectParameter>();
        var subParams = ((ObjectParameter)result["user"]).Properties.ToDictionary(p => p.Name);
        subParams["name"].Required.Should().BeTrue();
        subParams["age"].Required.Should().BeFalse();
    }

    [Fact]
    public void EmptySchema_ReturnsEmpty()
    {
        SchemaParser.ParseModelProperties(new Dictionary<string, object?>()).Should().BeEmpty();
    }

    [Fact]
    public void SchemaWithoutProperties_ReturnsEmpty()
    {
        var schema = Obj(("title", "Test Schema"), ("description", "A test schema without properties"));
        SchemaParser.ParseModelProperties(schema).Should().BeEmpty();
    }
}
