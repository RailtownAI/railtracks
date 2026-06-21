using Railtracks.Exceptions;

namespace Railtracks.Llm;

/// <summary>
/// Base class for all LLM exceptions. Ported from Python <c>RTLLMError</c>.
/// </summary>
public class LlmException : RailtracksException
{
    public LlmException() { }

    public LlmException(string message) : base(message) { }

    public LlmException(string message, Exception innerException)
        : base(message, innerException) { }
}

/// <summary>
/// Raised when an error occurs during an LLM call that is being retried.
/// Ported from Python <c>RetryError</c>.
/// </summary>
public class RetryException : LlmException
{
    public RetryException(
        string retryMethod,
        string message,
        IReadOnlyList<string> notes,
        IReadOnlyList<Exception> exceptionList)
        : base($"LLM call failed after retries from {retryMethod} retry: {message}")
    {
        DetailMessage = message;
        Notes = notes;
        ExceptionList = exceptionList;
    }

    public string DetailMessage { get; }
    public IReadOnlyList<string> Notes { get; }
    public IReadOnlyList<Exception> ExceptionList { get; }
}
