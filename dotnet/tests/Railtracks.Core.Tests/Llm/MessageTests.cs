using FluentAssertions;
using Railtracks.Llm;
using Xunit;

namespace Railtracks.Tests.Llm;

// Ported from tests/unit_tests/llm/test_message.py
public class MessageStructureTests
{
    [Theory]
    [InlineData("Hello", "user", "user: Hello")]
    [InlineData("System message", "system", "system: System message")]
    [InlineData("Assistant response", "assistant", "assistant: Assistant response")]
    public void ToString_RendersRoleAndContent(string content, string role, string expected)
    {
        Message message = role switch
        {
            "user" => new UserMessage(content),
            "system" => new SystemMessage(content),
            "assistant" => new AssistantMessage(content),
            _ => throw new InvalidOperationException("Invalid role"),
        };

        message.ToString().Should().Be(expected);
    }

    [Fact]
    public void SystemMessage_ExposesContentAndRole()
    {
        var message = new SystemMessage("System message");
        message.Content.Should().Be("System message");
        message.Role.Should().Be(Role.System);
        message.ToString().Should().Be("system: System message");
    }

    [Fact]
    public void AssistantMessage_ExposesContentAndRole()
    {
        var message = new AssistantMessage("Assistant response");
        message.Content.Should().Be("Assistant response");
        message.Role.Should().Be(Role.Assistant);
        message.ToString().Should().Be("assistant: Assistant response");
    }

    [Fact]
    public void ToolMessage_WrapsToolResponse()
    {
        var toolResponse = new ToolResponse("123", "tool1", "result");
        var message = new ToolMessage(toolResponse);

        message.Content.Should().Be(toolResponse);
        message.Role.Should().Be(Role.Tool);
        message.ToString().Should().Be($"tool: {toolResponse}");
        message.Response.Name.Should().Be("tool1");
        message.Response.Result.Should().Be("result");
        message.Response.Identifier.Should().Be("123");
    }

    [Fact]
    public void UserMessage_NullContent_Throws()
    {
        var act = () => new UserMessage((string?)null);
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void SystemMessage_NullContent_Throws()
    {
        var act = () => new SystemMessage(null!);
        act.Should().Throw<ArgumentException>();
    }

    [Fact]
    public void ToolMessage_NonToolResponseContent_Throws()
    {
        // The Python test passes a string; C#'s typed ctor only admits a ToolResponse,
        // so the equivalent invalid input is a null content.
        var act = () => new ToolMessage(null!);
        act.Should().Throw<ArgumentException>();
    }
}

// Ported from the offline (non-network) Attachment tests in test_message.py.
public class AttachmentTests
{
    [Theory]
    [InlineData(".jpg", "jpeg")]
    [InlineData(".jpeg", "jpeg")]
    [InlineData(".png", "png")]
    [InlineData(".gif", "gif")]
    [InlineData(".webp", "webp")]
    [InlineData(".PNG", "png")]
    public void LocalFile_ClassifiesImageFormats(string extension, string mime)
    {
        var path = Path.Combine(Path.GetTempPath(), $"test_{Guid.NewGuid():N}{extension}");
        File.WriteAllBytes(path, "fake image data"u8.ToArray());
        try
        {
            var attachment = new Attachment(path);
            attachment.Type.Should().Be("local");
            attachment.Modality.Should().Be("image");
            attachment.Encoding.Should().NotBeNull();
            attachment.Encoding.Should().Contain($"data:image/{mime};base64,");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void LocalFile_UnsupportedFormat_Throws()
    {
        var path = Path.Combine(Path.GetTempPath(), $"test_{Guid.NewGuid():N}.txt");
        File.WriteAllBytes(path, "fake data"u8.ToArray());
        try
        {
            var act = () => new Attachment(path);
            act.Should().Throw<ArgumentException>().WithMessage("*Unsupported attachment format*");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void LocalPdf_ClassifiesAsDocument()
    {
        var path = Path.Combine(Path.GetTempPath(), $"doc_{Guid.NewGuid():N}.pdf");
        File.WriteAllBytes(path, "%PDF-1.4\n%fake pdf body\n%%EOF"u8.ToArray());
        try
        {
            var attachment = new Attachment(path);
            attachment.Type.Should().Be("local");
            attachment.Modality.Should().Be("document");
            attachment.MimeType.Should().Be("application/pdf");
            attachment.Encoding.Should().StartWith("data:application/pdf;base64,");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void Base64Pdf_ClassifiesAsDataUriDocument()
    {
        var b64 = Convert.ToBase64String("%PDF-1.4\n%fake pdf body\n%%EOF"u8.ToArray());
        var attachment = new Attachment(b64);
        attachment.Type.Should().Be("data_uri");
        attachment.Modality.Should().Be("document");
        attachment.MimeType.Should().Be("application/pdf");
        attachment.Filename.Should().BeNull();
        attachment.Encoding.Should().StartWith("data:application/pdf;base64,");
    }

    [Fact]
    public void DataUriPdf_PreservedAsIs()
    {
        var b64 = Convert.ToBase64String("%PDF-1.4\n%fake pdf body\n%%EOF"u8.ToArray());
        var dataUri = $"data:application/pdf;base64,{b64}";
        var attachment = new Attachment(dataUri);
        attachment.Type.Should().Be("data_uri");
        attachment.Modality.Should().Be("document");
        attachment.MimeType.Should().Be("application/pdf");
        attachment.Encoding.Should().Be(dataUri);
    }

    [Fact]
    public void DataUriPdf_MixedCaseMime_ClassifiedAsDocument()
    {
        var b64 = Convert.ToBase64String("%PDF-1.4\n%fake pdf body\n%%EOF"u8.ToArray());
        var dataUri = $"data:Application/PDF;base64,{b64}";
        var attachment = new Attachment(dataUri);
        attachment.Modality.Should().Be("document");
        attachment.MimeType.Should().Be("application/pdf");
    }

    [Fact]
    public void Url_Png_ClassifiedAsImageNoFetch()
    {
        const string url = "https://example.com/image.png";
        var attachment = new Attachment(url);
        attachment.Url.Should().Be(url);
        attachment.Type.Should().Be("url");
        attachment.Modality.Should().Be("image");
        attachment.MimeType.Should().Be("image/png");
        attachment.Filename.Should().Be("image.png");
        attachment.Encoding.Should().BeNull();
    }

    [Fact]
    public void Url_WithQueryString_ParsesExtension()
    {
        var attachment = new Attachment("https://example.com/photo.png?token=abc&x=1");
        attachment.Type.Should().Be("url");
        attachment.Modality.Should().Be("image");
        attachment.MimeType.Should().Be("image/png");
        attachment.Filename.Should().Be("photo.png");
    }

    [Fact]
    public void DataUriImage_PreservedAsIs()
    {
        const string dataUri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA";
        var attachment = new Attachment(dataUri);
        attachment.Url.Should().Be("...");
        attachment.Encoding.Should().Be(dataUri);
        attachment.Type.Should().Be("data_uri");
    }

    [Fact]
    public void PdfUrl_WithoutTrustUrls_Throws()
    {
        var act = () => new Attachment("https://example.com/docs/report.pdf");
        act.Should().Throw<ArgumentException>().WithMessage("*trustUrls=true*");
    }

    [Fact]
    public void NullUrl_Throws()
    {
        var act = () => new Attachment(null!);
        act.Should().Throw<ArgumentException>().WithMessage("*url parameter must be a string*");
    }
}

public class UserMessageAttachmentTests
{
    [Fact]
    public void SingleAttachment_IsLocal()
    {
        var path = Path.Combine(Path.GetTempPath(), $"test_{Guid.NewGuid():N}.png");
        File.WriteAllBytes(path, new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A });
        try
        {
            var message = new UserMessage("Check this", path);
            message.Content.Should().Be("Check this");
            message.Attachment.Should().HaveCount(1);
            message.Attachment![0].Type.Should().Be("local");
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void NoAttachment_IsNull()
    {
        var message = new UserMessage("Just text");
        message.Attachment.Should().BeNull();
    }

    [Theory]
    [InlineData("https://example.com/image.png", "url")]
    [InlineData("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA", "data_uri")]
    public void AttachmentTypes_AreClassified(string attachment, string expectedType)
    {
        var message = new UserMessage("Test", attachment);
        message.Attachment.Should().NotBeNull();
        message.Attachment![0].Type.Should().Be(expectedType);
    }
}
