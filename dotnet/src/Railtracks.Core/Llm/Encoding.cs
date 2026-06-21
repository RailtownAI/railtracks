using System.Text;
using System.Text.RegularExpressions;

namespace Railtracks.Llm;

/// <summary>One of the three attachment source kinds. Ported from <c>detect_source</c>.</summary>
public enum AttachmentSource
{
    Local,
    Url,
    DataUri,
}

/// <summary>
/// Encoding/detection helpers for attachments. Ported from the Python
/// <c>railtracks.llm.encoding</c> and <c>attachment_formats</c> modules.
/// </summary>
public static class AttachmentEncoding
{
    private static readonly Regex DataUriHeader = new(
        @"^data:(image/[a-z0-9.+-]+|application/pdf);base64,$",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex Base64Chars = new(
        @"^[A-Za-z0-9+/=\s]+$", RegexOptions.Compiled);

    private static readonly Regex Base64UrlSafeChars = new(
        @"^[A-Za-z0-9\-_=\s]+$", RegexOptions.Compiled);

    /// <summary>
    /// Hook for fetching the bytes of a URL. Defaults to <see cref="DefaultUrlFetcher"/>.
    /// Tests override this to avoid in-process network I/O (the Python tests monkeypatch
    /// <c>urllib</c>; in C# the seam is this delegate).
    /// </summary>
    public static Func<string, double, byte[]> UrlFetcher { get; set; } = DefaultUrlFetcher;

    private static byte[] DefaultUrlFetcher(string url, double timeoutSeconds)
    {
        using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(timeoutSeconds) };
        return client.GetByteArrayAsync(url).GetAwaiter().GetResult();
    }

    /// <summary>Detects whether a string is a local file, URL, or data URI / base64 payload.</summary>
    public static AttachmentSource DetectSource(string path)
    {
        if (path.StartsWith("data:", StringComparison.Ordinal))
            return AttachmentSource.DataUri;

        if (IsBase64Attachment(path))
            return AttachmentSource.DataUri;

        var scheme = GetUriScheme(path);

        if (scheme is "http" or "https" or "ftp" or "ftps")
            return AttachmentSource.Url;

        // No scheme, "file", or a single-letter scheme on Windows (a drive letter like C:).
        if (string.IsNullOrEmpty(scheme)
            || scheme == "file"
            || (scheme.Length == 1 && OperatingSystem.IsWindows()))
        {
            return AttachmentSource.Local;
        }

        throw new ArgumentException($"Could not determine image source type for: {path}");
    }

    /// <summary>Base64-encodes the bytes at a local path or URL. Ported from <c>encode</c>.</summary>
    public static string Encode(string path, double timeout = 10.0)
    {
        var source = DetectSource(path);
        string encoding = source switch
        {
            AttachmentSource.Local => EncodeLocal(path),
            AttachmentSource.Url => Convert.ToBase64String(UrlFetcher(path, timeout)),
            AttachmentSource.DataUri => throw new ArgumentException("Data is already in base64 encoded format."),
            _ => throw new ArgumentException($"Unsupported source type: {source}"),
        };

        if (string.IsNullOrEmpty(encoding))
            throw new ArgumentException("Failed to encode image.");
        return encoding;
    }

    private static string EncodeLocal(string path)
    {
        if (!File.Exists(path))
            throw new FileNotFoundException($"File not found: {path}", path);
        return Convert.ToBase64String(File.ReadAllBytes(path));
    }

    /// <summary>
    /// If the input is a valid data URI, return it normalized; otherwise treat it as plain
    /// base64, sniff the MIME type, and construct a header. Ported from <c>ensure_data_uri</c>.
    /// </summary>
    public static string EnsureDataUri(string base64OrDataUri)
    {
        var s = base64OrDataUri.Trim();
        if (s.StartsWith("data:", StringComparison.Ordinal))
        {
            var commaIndex = s.IndexOf(',');
            if (commaIndex < 0)
                throw new ArgumentException(
                    "Incomplete data URI: missing comma separating header and base64 payload");

            var header = s[..commaIndex];
            var payload = s[(commaIndex + 1)..];
            var headerWithComma = header + ",";
            if (!DataUriHeader.IsMatch(headerWithComma))
            {
                throw new ArgumentException(
                    "Malformed data URI header. Expected format like 'data:image/png;base64,' " +
                    $"or 'data:application/pdf;base64,'. Got: {headerWithComma}");
            }

            return headerWithComma + payload;
        }

        if (!TryDecodeBase64(s, out var decoded))
            throw new ArgumentException("Provided string is not valid base64 or a data URI");

        var mime = DetectMimeFromBytes(decoded);
        if (mime is null)
        {
            throw new ArgumentException(
                "Could not detect MIME type from provided base64 data. Provide a proper data URI " +
                "or a supported attachment (image or PDF).");
        }

        return $"data:{mime};base64,{s}";
    }

    private static bool IsBase64Attachment(string s)
    {
        var stripped = s.Trim();
        if (!Base64Chars.IsMatch(stripped) && !Base64UrlSafeChars.IsMatch(stripped))
            return false;

        return TryDecodeBase64(stripped, out var decoded) && DetectMimeFromBytes(decoded) is not null;
    }

    private static bool TryDecodeBase64(string s, out byte[] decoded)
    {
        var stripped = Regex.Replace(s.Trim(), @"\s", "").Replace('-', '+').Replace('_', '/');
        var padded = stripped.PadRight(stripped.Length + (4 - stripped.Length % 4) % 4, '=');
        try
        {
            decoded = Convert.FromBase64String(padded);
            return decoded.Length > 0;
        }
        catch (FormatException)
        {
            decoded = Array.Empty<byte>();
            return false;
        }
    }

    /// <summary>
    /// Magic-byte MIME sniffing for the supported attachment formats. Ported from the
    /// Python <c>detect_attachment_mime_from_bytes</c> (which is driven by a YAML table).
    /// </summary>
    public static string? DetectMimeFromBytes(ReadOnlySpan<byte> data)
    {
        if (StartsWith(data, 0x89, 0x50, 0x4E, 0x47)) return "image/png"; // PNG
        if (StartsWith(data, 0xFF, 0xD8, 0xFF)) return "image/jpeg";       // JPEG
        if (StartsWith(data, 0x47, 0x49, 0x46, 0x38)) return "image/gif";  // GIF8
        if (StartsWith(data, 0x25, 0x50, 0x44, 0x46)) return "application/pdf"; // %PDF
        // WEBP: "RIFF"...."WEBP"
        if (data.Length >= 12
            && StartsWith(data, 0x52, 0x49, 0x46, 0x46)
            && data[8] == 0x57 && data[9] == 0x45 && data[10] == 0x42 && data[11] == 0x50)
        {
            return "image/webp";
        }

        return null;
    }

    private static bool StartsWith(ReadOnlySpan<byte> data, params byte[] prefix)
    {
        if (data.Length < prefix.Length) return false;
        for (var i = 0; i < prefix.Length; i++)
            if (data[i] != prefix[i]) return false;
        return true;
    }

    private static string GetUriScheme(string path)
    {
        if (Uri.TryCreate(path, UriKind.Absolute, out var uri))
        {
            // On Windows, an absolute file path like C:\x parses as a "file" URI with a drive.
            return uri.Scheme;
        }

        // Fall back to a manual scheme scan (handles "c:" drive prefixes etc.).
        var idx = path.IndexOf(':');
        if (idx <= 0) return string.Empty;
        var candidate = path[..idx];
        return Regex.IsMatch(candidate, @"^[A-Za-z][A-Za-z0-9+.\-]*$")
            ? candidate.ToLowerInvariant()
            : string.Empty;
    }

    internal static string Utf8(this byte[] bytes) => Encoding.UTF8.GetString(bytes);
}
