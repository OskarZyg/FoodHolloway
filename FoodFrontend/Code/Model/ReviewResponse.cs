namespace FoodFrontend.Code.Model;

public class ReviewResponse
{
    public string Uuid { get; set; } = string.Empty;
    public int Rating { get; set; }
    public string ReviewSubject { get; set; } = string.Empty;
    public string? Email { get; set; }
    public string? DisplayName { get; set; }
    public string CreatedAt { get; set; } = string.Empty;
    public string UpdatedAt { get; set; } = string.Empty;
}