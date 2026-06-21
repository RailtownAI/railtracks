using FluentAssertions;
using Railtracks.Llm.Tools;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported from tests/unit_tests/llm/tools/parameters/test__base.py
public class ParameterBaseTests
{
    [Fact]
    public void InitAndProperties()
    {
        var p = new Parameter("foo", description: "desc", required: false, @default: "bar",
            @enum: new object?[] { "bar", "baz" });
        p.Name.Should().Be("foo");
        p.Description.Should().Be("desc");
        p.Required.Should().BeFalse();
        p.Default.Should().Be("bar");
        p.Enum.Should().Equal("bar", "baz");
    }

    [Fact]
    public void ToJsonSchema_IncludesTypeDescriptionEnumDefault()
    {
        var p = new Parameter("foo", paramType: "string", description: "desc", required: true,
            @default: "bar", @enum: new object?[] { "bar", "baz" }, defaultPresent: true);
        var schema = p.ToJsonSchema();
        schema["type"].Should().Be("string");
        schema["description"].Should().Be("desc");
        schema["enum"].Should().BeEquivalentTo(new object?[] { "bar", "baz" });
        schema["default"].Should().Be("bar");
    }

    [Fact]
    public void FromClrType_MapsBuiltins()
    {
        ParameterTypeExtensions.FromClrType(typeof(string)).Should().Be(ParameterType.String);
        ParameterTypeExtensions.FromClrType(typeof(int)).Should().Be(ParameterType.Integer);
        ParameterTypeExtensions.FromClrType(typeof(double)).Should().Be(ParameterType.Float);
        ParameterTypeExtensions.FromClrType(typeof(bool)).Should().Be(ParameterType.Boolean);
        ParameterTypeExtensions.FromClrType(typeof(int[])).Should().Be(ParameterType.Array);
        ParameterTypeExtensions.FromClrType(typeof(Dictionary<string, int>)).Should().Be(ParameterType.Object);
    }

    [Fact]
    public void Constructor_AcceptsClrType_String()
    {
        var p = new Parameter("query", description: "The search query string.", paramType: typeof(string));
        p.ParamType.Should().Be("string");
        p.ToJsonSchema()["type"].Should().Be("string");
    }

    [Fact]
    public void Constructor_AcceptsClrType_Int()
    {
        var p = new Parameter("n", description: "A number.", paramType: typeof(int));
        p.ParamType.Should().Be("integer");
        p.ToJsonSchema()["type"].Should().Be("integer");
    }

    [Fact]
    public void Constructor_AcceptsMixedTypeList()
    {
        var p = new Parameter("x", paramType: new object[] { typeof(string), "null" });
        p.ParamType.Should().BeOfType<List<string>>()
            .Which.Should().Equal("string", "null");
    }
}

// Ported from test_array_parameter.py / test_object_parameter.py / test_ref_parameter.py / test_union_parameter.py
public class ArrayParameterTests
{
    [Fact]
    public void ToJsonSchema_BasicArray()
    {
        var arr = new ArrayParameter("arr",
            items: new Parameter("item", paramType: ParameterType.String),
            description: "desc", required: false, @default: new List<string> { "a" }, maxItems: 3);
        var schema = arr.ToJsonSchema();
        schema["type"].Should().Be("array");
        ((Dictionary<string, object?>)schema["items"]!)["type"].Should().Be("string");
        schema["description"].Should().Be("desc");
        schema["default"].Should().BeEquivalentTo(new List<string> { "a" });
        schema["maxItems"].Should().Be(3);
    }

    [Fact]
    public void ToString_ContainsTypeAndName()
    {
        var arr = new ArrayParameter("arr", new Parameter("item", paramType: ParameterType.String));
        arr.ToString().Should().Contain("ArrayParameter").And.Contain("arr");
    }
}

public class ObjectParameterTests
{
    [Fact]
    public void ToJsonSchema_BasicObject()
    {
        var obj = new ObjectParameter("obj",
            properties: new List<Parameter>
            {
                new("foo", required: true, paramType: ParameterType.String),
                new("bar", required: false, paramType: ParameterType.String),
            },
            description: "desc", required: true, additionalProperties: true);
        var schema = obj.ToJsonSchema();
        schema["type"].Should().Be("object");
        var props = (Dictionary<string, object?>)schema["properties"]!;
        props.Should().ContainKey("foo");
        ((Dictionary<string, object?>)props["foo"]!)["type"].Should().Be("string");
        schema["description"].Should().Be("desc");
        schema["additionalProperties"].Should().Be(true);
        ((List<string>)schema["required"]!).Should().Contain("foo");
    }

    [Fact]
    public void ToString_ContainsTypeAndName()
    {
        var obj = new ObjectParameter("obj", new List<Parameter>());
        obj.ToString().Should().Contain("ObjectParameter").And.Contain("obj");
    }
}

public class RefParameterTests
{
    [Fact]
    public void ToJsonSchema_BasicRef()
    {
        var refParam = new RefParameter("foo", refPath: "#/$defs/Bar", description: "desc", required: false);
        var schema = refParam.ToJsonSchema();
        schema["$ref"].Should().Be("#/$defs/Bar");
        schema["description"].Should().Be("desc");
    }

    [Fact]
    public void ToString_ContainsTypeNameAndRef()
    {
        var refParam = new RefParameter("foo", "#/$defs/Bar");
        refParam.ToString().Should().Contain("RefParameter").And.Contain("foo").And.Contain("#/$defs/Bar");
    }
}

public class UnionParameterTests
{
    [Fact]
    public void ToJsonSchema_BasicUnion()
    {
        var p1 = new Parameter("foo", paramType: "string");
        var p2 = new Parameter("bar", paramType: "integer");
        var union = new UnionParameter("baz", new List<Parameter> { p1, p2 },
            description: "desc", required: true, defaultPresent: true, @default: 123);
        var schema = union.ToJsonSchema();
        schema.Should().ContainKey("anyOf");
        var anyOf = (List<Dictionary<string, object?>>)schema["anyOf"]!;
        anyOf.Should().ContainEquivalentOf(new Dictionary<string, object?> { ["type"] = "string" });
        anyOf.Should().ContainEquivalentOf(new Dictionary<string, object?> { ["type"] = "integer" });
        schema["description"].Should().Be("desc");
        schema["default"].Should().Be(123);
    }

    [Fact]
    public void NestedUnion_Throws()
    {
        var p1 = new Parameter("foo", paramType: "string");
        var act = () => new UnionParameter("baz",
            new List<Parameter> { p1, new UnionParameter("bad", new List<Parameter> { p1 }) });
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void ToString_ContainsTypeAndName()
    {
        var union = new UnionParameter("baz", new List<Parameter>
        {
            new("foo", paramType: "string"),
            new("bar", paramType: "integer"),
        });
        union.ToString().Should().Contain("UnionParameter").And.Contain("baz");
    }
}
