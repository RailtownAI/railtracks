using FluentAssertions;
using Railtracks.Llm;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported from tests/unit_tests/llm/test_history.py
public class MessageHistoryTests
{
    [Fact]
    public void ToString_JoinsMessagesWithNewline()
    {
        var history = new MessageHistory
        {
            new Message("Hello", Role.User),
            new Message("Hi there!", Role.Assistant),
        };

        history.ToString().Should().Be("user: Hello\nassistant: Hi there!");
    }

    [Fact]
    public void ToString_SingleUserMessage()
    {
        var history = new MessageHistory
        {
            new UserMessage("What is going on in this beautiful world?"),
        };

        history.ToString().Should().Be("user: What is going on in this beautiful world?");
    }

    [Fact]
    public void ToString_MultilineHistory()
    {
        var history = new MessageHistory
        {
            new UserMessage("What is going on in this beautiful world?"),
            new AssistantMessage("Nothing much as of now"),
        };

        history.ToString().Should().Be(
            "user: What is going on in this beautiful world?\nassistant: Nothing much as of now");
    }

    [Fact]
    public void RemovedSystemMessages_FiltersSystemRole()
    {
        var history = new MessageHistory
        {
            new SystemMessage("be helpful"),
            new UserMessage("hi"),
        };

        var filtered = history.RemovedSystemMessages();
        filtered.Should().ContainSingle();
        filtered[0].Role.Should().Be(Role.User);
    }
}

// Ported from tests/unit_tests/llm/test_response.py
public class MessageInfoTests
{
    [Fact]
    public void TotalTokens_SumsWhenBothPresent()
    {
        new MessageInfo(inputTokens: 3, outputTokens: 4).TotalTokens.Should().Be(7);
    }

    [Fact]
    public void TotalTokens_NullWhenEitherMissing()
    {
        new MessageInfo(inputTokens: null, outputTokens: 5).TotalTokens.Should().BeNull();
        new MessageInfo(inputTokens: 2, outputTokens: null).TotalTokens.Should().BeNull();
    }

    [Fact]
    public void ToString_ContainsFields()
    {
        var info = new MessageInfo(1, 2, 0.5, "test-model", 0.01, "fp123");
        var s = info.ToString();
        s.Should().Contain("MessageInfo(");
        s.Should().Contain("input_tokens=1");
        s.Should().Contain("output_tokens=2");
        s.Should().Contain("latency=0.5");
        s.Should().Contain("model_name='test-model'");
        s.Should().Contain("total_cost=0.01");
        s.Should().Contain("system_fingerprint='fp123'");
    }
}

public class ResponseTests
{
    [Fact]
    public void ToString_UsesMessageString()
    {
        var message = new AssistantMessage("Hello there.");
        var response = new Response(message);
        response.ToString().Should().Be(message.ToString());
    }

    [Fact]
    public void ToRepr_IncludesComponents()
    {
        var response = new Response(new AssistantMessage("Hi"), new MessageInfo(1, 2));
        var s = response.ToRepr();
        s.Should().Contain("Response(");
        s.Should().Contain("message=");
        s.Should().Contain("message_info=");
    }

    [Fact]
    public void Message_IsReferenceEqual()
    {
        var message = new AssistantMessage("Streaming test.");
        var response = new Response(message);
        response.Message.Should().BeSameAs(message);
    }

    [Fact]
    public void NullMessage_Throws()
    {
        var act = () => new Response(null!);
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void MessageInfo_AccessibleWhenProvided()
    {
        var info = new MessageInfo(5, 7, 0.12, "test-model", 0.5);
        var response = new Response(new AssistantMessage("Info test."), info);
        response.MessageInfo.Should().BeSameAs(info);
        response.MessageInfo.InputTokens.Should().Be(5);
        response.MessageInfo.OutputTokens.Should().Be(7);
        response.MessageInfo.Latency.Should().Be(0.12);
        response.MessageInfo.ModelName.Should().Be("test-model");
        response.MessageInfo.TotalCost.Should().Be(0.5);
    }

    [Fact]
    public void DefaultMessageInfo_UsedWhenNotProvided()
    {
        var response = new Response(new AssistantMessage("Default info test."));
        var info = response.MessageInfo;
        info.Should().BeOfType<MessageInfo>();
        info.InputTokens.Should().BeNull();
        info.OutputTokens.Should().BeNull();
        info.Latency.Should().BeNull();
        info.ModelName.Should().BeNull();
        info.TotalCost.Should().BeNull();
        info.SystemFingerprint.Should().BeNull();
    }
}
