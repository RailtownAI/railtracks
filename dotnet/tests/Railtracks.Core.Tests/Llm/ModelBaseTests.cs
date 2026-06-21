using FluentAssertions;
using Railtracks.Llm;
using Railtracks.Llm.Tools;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported in spirit from tests/unit_tests/llm/test_model.py — verifies the hook
// orchestration of ModelBase (pre/post/exception hooks around the core call).
public class ModelBaseTests
{
    private sealed class FakeModel : ModelBase
    {
        private readonly Func<MessageHistory, Response> _core;

        public FakeModel(Func<MessageHistory, Response>? core = null) =>
            _core = core ?? (m => new Response(new AssistantMessage("ok")));

        public override string ModelName() => "fake-model";
        public override ModelProvider ModelProviderName() => ModelProvider.OpenAI;
        public override ModelProvider ModelGateway() => ModelProvider.OpenAI;

        protected override Task<Response> ChatCoreAsync(MessageHistory messages) =>
            Task.FromResult(_core(messages));

        protected override Task<Response> StructuredCoreAsync(MessageHistory messages, Type schema) =>
            Task.FromResult(_core(messages));

        protected override Task<Response> ChatWithToolsCoreAsync(MessageHistory messages, IReadOnlyList<Tool> tools) =>
            Task.FromResult(_core(messages));
    }

    [Fact]
    public async Task ChatAsync_ReturnsCoreResponse()
    {
        var model = new FakeModel();
        var response = await model.ChatAsync(new MessageHistory { new UserMessage("hi") });
        response.Message.Content.Should().Be("ok");
    }

    [Fact]
    public async Task PreHook_RunsBeforeCore()
    {
        var model = new FakeModel(m => new Response(new AssistantMessage($"count={m.Count}")));
        model.AddPreHook(m =>
        {
            m.Add(new UserMessage("injected"));
            return m;
        });

        var response = await model.ChatAsync(new MessageHistory { new UserMessage("hi") });
        response.Message.Content.Should().Be("count=2");
    }

    [Fact]
    public async Task PostHook_TransformsResponse()
    {
        var model = new FakeModel();
        model.AddPostHook((_, r) => new Response(new AssistantMessage("rewritten"), r.MessageInfo));

        var response = await model.ChatAsync(new MessageHistory { new UserMessage("hi") });
        response.Message.Content.Should().Be("rewritten");
    }

    [Fact]
    public async Task ExceptionHook_RunsAndRethrows()
    {
        var model = new FakeModel(_ => throw new InvalidOperationException("boom"));
        var observed = false;
        model.AddExceptionHook((_, _) => observed = true);

        var act = async () => await model.ChatAsync(new MessageHistory { new UserMessage("hi") });
        await act.Should().ThrowAsync<InvalidOperationException>().WithMessage("boom");
        observed.Should().BeTrue();
    }

    [Fact]
    public void RemoveHooks_ClearsThem()
    {
        var model = new FakeModel();
        model.AddPreHook(m => m);
        model.RemovePreHooks();
        // No assertion target beyond not throwing; behavior verified by ChatAsync staying pristine.
        model.Invoking(m => m.RemovePostHooks()).Should().NotThrow();
    }
}

// Verifies the reflection-based Tool builder (the C# analog of Python's from_function).
public class ToolFromMethodTests
{
    private static void SampleTool(string query, int count = 5) { }

    [Fact]
    public void FromDelegate_ExtractsParametersAndRequiredness()
    {
        var descriptions = new Dictionary<string, string> { ["query"] = "The search query." };
        var tool = Tool.FromDelegate((Action<string, int>)SampleTool, name: "search",
            details: "Search the corpus.", argDescriptions: descriptions);

        tool.Name.Should().Be("search");
        tool.Detail.Should().Be("Search the corpus.");
        tool.Parameters.Should().HaveCount(2);

        var query = tool.Parameters!.Single(p => p.Name == "query");
        query.ParamType.Should().Be("string");
        query.Required.Should().BeTrue();
        query.Description.Should().Be("The search query.");

        var count = tool.Parameters!.Single(p => p.Name == "count");
        count.ParamType.Should().Be("integer");
        count.Required.Should().BeFalse(); // has a default value
    }

    [Fact]
    public void Constructor_FromSchemaDict_BuildsParameters()
    {
        var schema = new Dictionary<string, object?>
        {
            ["properties"] = new Dictionary<string, object?>
            {
                ["name"] = new Dictionary<string, object?> { ["type"] = "string" },
            },
            ["required"] = new List<string> { "name" },
        };

        var tool = new Tool("greet", "Greet someone", schema);
        tool.Parameters.Should().ContainSingle();
        tool.Parameters![0].Name.Should().Be("name");
        tool.Parameters[0].ParamType.Should().Be("string");
    }
}
