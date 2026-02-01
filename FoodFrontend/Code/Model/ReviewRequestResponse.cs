using System.Text.Json.Serialization;

namespace FoodFrontend.Code.Model;

public class ReviewRequestResponse
{
    [JsonPropertyName("uuid")]
    public string Uuid { get; set; }
    public string FsaId { get; set; } = string.Empty;
    public int Rating { get; set; }
    public string ReviewSubject { get; set; } = string.Empty;
}