namespace FoodFrontend.Code.Model;

public class ReviewListResponse
{
    public string FsaId { get; set; } = string.Empty;
    public int Count { get; set; }
    public List<ReviewResponse> Reviews { get; set; } = new();
}