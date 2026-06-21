namespace Railtracks.Exceptions;

/// <summary>
/// Base class for all Railtracks exceptions to inherit from.
/// Ported from the Python <c>RTError</c> base class.
/// </summary>
public class RailtracksException : Exception
{
    // ANSI color codes for terminal output (ported from RTError).
    public const string BoldRed = "[1m[91m";
    public const string Red = "[91m";
    public const string BoldGreen = "[1m[92m";
    public const string Green = "[92m";
    public const string Reset = "[0m";

    public RailtracksException() { }

    public RailtracksException(string message) : base(message) { }

    public RailtracksException(string message, Exception innerException)
        : base(message, innerException) { }

    /// <summary>Helper to colorize text for terminal output.</summary>
    protected static string Color(string text, string colorCode) => $"{colorCode}{text}{Reset}";
}
