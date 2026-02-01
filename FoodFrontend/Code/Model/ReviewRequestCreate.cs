namespace FoodFrontend.Code.Model;

public class ReviewRequestCreate
{
    public int Rating { get; set; }
    public string ReviewSubject { get; set; } = string.Empty;
}
