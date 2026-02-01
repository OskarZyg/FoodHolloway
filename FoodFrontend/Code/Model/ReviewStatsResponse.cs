namespace FoodFrontend.Code.Model;

public class ReviewStatsResponse
{
    public string FsaId { get; set; } = string.Empty;
    public string ReviewSubject { get; set; } = string.Empty;
    public int TotalReviews { get; set; }
    public int CompletedReviews { get; set; }
    public int PendingReviews { get; set; }
    public double AverageRating { get; set; }
    public int MinRating { get; set; }
    public int MaxRating { get; set; }
    public Dictionary<int, int> RatingDistribution { get; set; } = new();
}