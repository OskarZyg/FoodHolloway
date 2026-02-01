using System.Collections.ObjectModel;
using System.Net.Http.Json;
using System.Text.Json;
using FoodFrontend.Code.Model;
using OpenLayers.Blazor;

namespace FoodFrontend.Code.Services;

public class PoiQueryService
{
    private readonly HttpClient _client;
    private readonly IConfiguration _config;
    
    public PoiQueryService(HttpClient client, IConfiguration config)
    {
        _client = client;
        _config = config;
        
        _client.BaseAddress = new Uri(config["ApiBaseUrl"]!);
    }
    
    public async Task<Collection<LitePoi>> QueryPoi(Coordinate point)
    {
        HttpRequestMessage msg = new HttpRequestMessage(HttpMethod.Get, $"/places/{point.Longitude}/{point.Latitude}/");
        HttpResponseMessage resp = await _client.SendAsync(msg);
        return (await JsonSerializer.DeserializeAsync<Collection<LitePoi>>(await resp.Content.ReadAsStreamAsync()))!;
    }

    public async Task<Poi> QuerySpecificPoi(LitePoi poi)
    {
        return await QuerySpecificPoi(poi.FoodSafetyAgencyId);
    }

    public async Task<Poi> QuerySpecificPoi(string fsaId)
    {
        HttpRequestMessage msg = new HttpRequestMessage(HttpMethod.Get, $"/place/{fsaId}/");
        HttpResponseMessage resp = await _client.SendAsync(msg);
        return (await JsonSerializer.DeserializeAsync<Poi>(await resp.Content.ReadAsStreamAsync()))!;
    }

    public async Task<List<LitePoi>> QueryPoiFromString(string query)
    {
        HttpRequestMessage msg = new HttpRequestMessage(HttpMethod.Get, $"/search/{query}");
        HttpResponseMessage resp = await _client.SendAsync(msg);
        return (await JsonSerializer.DeserializeAsync<List<LitePoi>>(await resp.Content.ReadAsStreamAsync()))!;
    }

    /// <summary>
    /// Create a new review request for a place.
    /// </summary>
    /// <param name="fsaId">Food Safety Agency ID</param>
    /// <param name="rating">Rating between 1 and 5</param>
    /// <param name="reviewSubject">Description of what is being reviewed</param>
    /// <returns>The created review request with UUID</returns>
    public async Task<ReviewRequestResponse> CreateReviewRequest(string fsaId, int rating, string reviewSubject)
    {
        var requestBody = new ReviewRequestCreate
        {
            Rating = rating,
            ReviewSubject = reviewSubject
        };

        HttpRequestMessage msg = new HttpRequestMessage(HttpMethod.Put, $"/place/{fsaId}/review");
        msg.Content = JsonContent.Create(requestBody);
        
        HttpResponseMessage resp = await _client.SendAsync(msg);
        resp.EnsureSuccessStatusCode();
        
        return (await JsonSerializer.DeserializeAsync<ReviewRequestResponse>(await resp.Content.ReadAsStreamAsync()))!;
    }

    /// <summary>
    /// Get all reviews for a specific place.
    /// </summary>
    /// <param name="fsaId">Food Safety Agency ID</param>
    /// <returns>List of reviews for the place</returns>
    public async Task<ReviewListResponse> GetReviewsForPlace(string fsaId)
    {
        HttpRequestMessage msg = new HttpRequestMessage(HttpMethod.Get, $"/place/{fsaId}/reviews");
        HttpResponseMessage resp = await _client.SendAsync(msg);
        resp.EnsureSuccessStatusCode();
        
        return (await JsonSerializer.DeserializeAsync<ReviewListResponse>(await resp.Content.ReadAsStreamAsync()))!;
    }

    /// <summary>
    /// Get review statistics for a specific place.
    /// </summary>
    /// <param name="fsaId">Food Safety Agency ID</param>
    /// <returns>Statistics including average rating and distribution</returns>
    public async Task<ReviewStatsResponse> GetReviewStatsForPlace(string fsaId)
    {
        HttpRequestMessage msg = new HttpRequestMessage(HttpMethod.Get, $"/place/{fsaId}/review/stats");
        HttpResponseMessage resp = await _client.SendAsync(msg);
        resp.EnsureSuccessStatusCode();
        
        return (await JsonSerializer.DeserializeAsync<ReviewStatsResponse>(await resp.Content.ReadAsStreamAsync()))!;
    }
}
