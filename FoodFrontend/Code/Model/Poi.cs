using System.Text.Json.Serialization;

namespace FoodFrontend.Code.Model;

public class Poi : LitePoi
{
    [JsonPropertyName("cuisine")]
    public required string? Cuisine { get; init; }
    
    [JsonPropertyName("star_rating")]
    public required double? StarRating { get; init; }
    
    [JsonPropertyName("opening_hours")]
    public required string? OpeningHours { get; init; }
    
    [JsonPropertyName("vegetarian")]
    public required bool? Vegetarian { get; init; }
    
    [JsonPropertyName("vegan")]
    public required bool? Vegan { get; init; }
    [JsonPropertyName("description")]
    public required string Description { get; init; }
}