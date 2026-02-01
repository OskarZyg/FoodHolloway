using System.Text.Json.Serialization;
using OpenLayers.Blazor;

namespace FoodFrontend.Code.Model;

public class LitePoi
{
    [JsonPropertyName("lat")]
    public required double Latitude { get; init; }
    [JsonPropertyName("lon")]
    public required double Longitude { get; init; }
    [JsonPropertyName("fsa_id")]
    public required string FoodSafetyAgencyId { get; init; }
    [JsonPropertyName("name")]
    public required string Name { get; init; }
    [JsonPropertyName("amenity")]
    public required string AmenityType { get; init; }

    public Coordinate Coordinate => new Coordinate(Longitude, Latitude);
}