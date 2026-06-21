using Railtracks.Llm.Tools;

namespace Railtracks.Llm;

/// <summary>
/// Base class for a model usable for chat, structured, and tool interactions.
/// Ported from the Python <c>ModelBase</c>.
/// <para>
/// Supports pre-hooks (modify messages before sending), post-hooks (modify the response
/// after receiving), and exception-hooks (observe exceptions). The Python sync/streaming
/// generator overloads collapse to async-first methods here; streaming is deferred to a
/// later slice. Concrete providers bind to <c>Microsoft.Extensions.AI.IChatClient</c>.
/// </para>
/// </summary>
public abstract class ModelBase
{
    private readonly List<Func<MessageHistory, MessageHistory>> _preHooks;
    private readonly List<Func<MessageHistory, Response, Response>> _postHooks;
    private readonly List<Action<MessageHistory, Exception>> _exceptionHooks;

    protected ModelBase(
        IEnumerable<Func<MessageHistory, MessageHistory>>? preHooks = null,
        IEnumerable<Func<MessageHistory, Response, Response>>? postHooks = null,
        IEnumerable<Action<MessageHistory, Exception>>? exceptionHooks = null)
    {
        _preHooks = preHooks?.ToList() ?? new List<Func<MessageHistory, MessageHistory>>();
        _postHooks = postHooks?.ToList() ?? new List<Func<MessageHistory, Response, Response>>();
        _exceptionHooks = exceptionHooks?.ToList() ?? new List<Action<MessageHistory, Exception>>();
    }

    public void AddPreHook(Func<MessageHistory, MessageHistory> hook) => _preHooks.Add(hook);
    public void AddPostHook(Func<MessageHistory, Response, Response> hook) => _postHooks.Add(hook);
    public void AddExceptionHook(Action<MessageHistory, Exception> hook) => _exceptionHooks.Add(hook);
    public void RemovePreHooks() => _preHooks.Clear();
    public void RemovePostHooks() => _postHooks.Clear();
    public void RemoveExceptionHooks() => _exceptionHooks.Clear();

    /// <summary>The name of the model being used.</summary>
    public abstract string ModelName();

    /// <summary>The provider that owns the model.</summary>
    public abstract ModelProvider ModelProviderName();

    /// <summary>The API distributor of the model (not necessarily the same as the provider).</summary>
    public abstract ModelProvider ModelGateway();

    public Task<Response> ChatAsync(MessageHistory messages) =>
        RunAsync(messages, ChatCoreAsync);

    public Task<Response> StructuredAsync(MessageHistory messages, Type schema) =>
        RunAsync(messages, m => StructuredCoreAsync(m, schema));

    public Task<Response> ChatWithToolsAsync(MessageHistory messages, IReadOnlyList<Tool> tools) =>
        RunAsync(messages, m => ChatWithToolsCoreAsync(m, tools));

    protected abstract Task<Response> ChatCoreAsync(MessageHistory messages);

    protected abstract Task<Response> StructuredCoreAsync(MessageHistory messages, Type schema);

    protected abstract Task<Response> ChatWithToolsCoreAsync(MessageHistory messages, IReadOnlyList<Tool> tools);

    private async Task<Response> RunAsync(MessageHistory messages, Func<MessageHistory, Task<Response>> core)
    {
        messages = RunPreHooks(messages);

        Response response;
        try
        {
            response = await core(messages).ConfigureAwait(false);
        }
        catch (Exception e)
        {
            RunExceptionHooks(messages, e);
            throw;
        }

        return RunPostHooks(messages, response);
    }

    private MessageHistory RunPreHooks(MessageHistory messages)
    {
        foreach (var hook in _preHooks)
            messages = hook(messages);
        return messages;
    }

    private Response RunPostHooks(MessageHistory messages, Response result)
    {
        foreach (var hook in _postHooks)
            result = hook(messages, result);
        return result;
    }

    private void RunExceptionHooks(MessageHistory messages, Exception exception)
    {
        foreach (var hook in _exceptionHooks)
            hook(messages, exception);
    }
}
