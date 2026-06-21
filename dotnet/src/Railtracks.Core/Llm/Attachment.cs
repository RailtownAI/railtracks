using System.Text.RegularExpressions;

namespace Railtracks.Llm;

/// <summary>
/// Represents an attachment to a message (image or PDF). Ported from the Python <c>Attachment</c>.
/// </summary>
public sealed class Attachment
{
    private static readonly IReadOnlyDictionary<string, string> ExtensionMimeMap =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            [".jpg"] = "image/jpeg",
            [".jpeg"] = "image/jpeg",
            [".png"] = "image/png",
            [".gif"] = "image/gif",
            [".webp"] = "image/webp",
            [".pdf"] = "application/pdf",
        };

    /// <summary>
    /// Hook for HEAD-probing a URL with no usable extension, returning (contentType, filename).
    /// Defaults to a no-op that returns (null, null); tests/integrations can override.
    /// (The Python version uses urllib; in C# this is the injection seam.)
    /// </summary>
    public static Func<string, double, (string? ContentType, string? Filename)> UrlProbe { get; set; }
        = (_, _) => (null, null);

    public Attachment(string url, bool trustUrls = false, double attachmentTimeout = 10.0)
    {
        if (url is null)
            throw new ArgumentException("The url parameter must be a string representing a file path or URL.", nameof(url));

        Url = url;
        Modality = "image";

        switch (AttachmentEncoding.DetectSource(url))
        {
            case AttachmentSource.Local:
                InitLocal(url);
                break;
            case AttachmentSource.Url:
                InitUrl(url, trustUrls, attachmentTimeout);
                break;
            case AttachmentSource.DataUri:
                InitDataUri(url);
                break;
        }
    }

    public string Url { get; private set; }
    public string? MimeType { get; private set; }
    public string Modality { get; private set; }
    public string? Encoding { get; private set; }
    public string? Filename { get; private set; }

    /// <summary>The source kind: "local", "url", or "data_uri" (matches the Python <c>type</c> field).</summary>
    public string Type { get; private set; } = string.Empty;

    private static string ModalityForMime(string mimeType) =>
        mimeType == "application/pdf" ? "document" : "image";

    private void InitLocal(string url)
    {
        var ext = Path.GetExtension(url).ToLowerInvariant();
        if (!ExtensionMimeMap.TryGetValue(ext, out var mime))
        {
            throw new ArgumentException(
                $"Unsupported attachment format: {ext}. Supported formats: {string.Join(", ", ExtensionMimeMap.Keys)}");
        }

        MimeType = mime;
        Modality = ModalityForMime(mime);
        Encoding = $"data:{mime};base64,{AttachmentEncoding.Encode(url)}";
        var name = Path.GetFileName(url);
        Filename = string.IsNullOrEmpty(name) ? null : name;
        Type = "local";
    }

    private void InitUrl(string url, bool trustUrls, double timeout)
    {
        var path = Uri.TryCreate(url, UriKind.Absolute, out var uri) ? uri.AbsolutePath : url;
        var ext = Path.GetExtension(path).ToLowerInvariant();
        string? probedFilename = null;

        if (ExtensionMimeMap.TryGetValue(ext, out var mime))
        {
            MimeType = mime;
        }
        else if (trustUrls)
        {
            var (probedCt, probedName) = UrlProbe(url, timeout);
            probedFilename = probedName;
            if (probedCt == "application/pdf" || (probedCt is not null && probedCt.StartsWith("image/", StringComparison.Ordinal)))
                MimeType = probedCt;
        }

        if (MimeType is not null)
            Modality = ModalityForMime(MimeType);

        var baseName = Path.GetFileName(path);
        Filename = probedFilename ?? (string.IsNullOrEmpty(baseName) ? null : baseName);

        if (Modality == "document")
        {
            if (!trustUrls)
            {
                throw new ArgumentException(
                    $"PDF URL attachments require trustUrls=true: '{Url}'. Constructing this attachment " +
                    "would fetch the URL in-process and embed its bytes into the LLM prompt, which is an " +
                    "SSRF/exfiltration surface for end-user-supplied URLs. Pass trustUrls=true only when the " +
                    "URL is developer-controlled; otherwise download the PDF first and pass a local file path " +
                    "or base64/data-URI payload.");
            }

            Encoding = $"data:{MimeType};base64,{AttachmentEncoding.Encode(url, timeout)}";
        }

        Type = "url";
    }

    private void InitDataUri(string url)
    {
        Url = "...";
        Encoding = AttachmentEncoding.EnsureDataUri(url);
        var header = Encoding.Split(',', 2)[0]; // "data:<mime>;base64"
        MimeType = header["data:".Length..].Split(';', 2)[0].ToLowerInvariant();
        Modality = ModalityForMime(MimeType);
        Type = "data_uri";
    }

    internal static readonly Regex FilenameRegex = new(
        "filename\\*?=(?:[^'\"]*'')?\"?([^\";]+)\"?", RegexOptions.Compiled);
}
