using FoodFrontend.Code.Model;
using FoodFrontend.Code.Services;
using Microsoft.AspNetCore.Components;

namespace FoodFrontend.Pages;

public partial class Search : ComponentBase
{    [Inject] public required PoiQueryService PoiQueryService { get; set; }
    
    SemaphoreSlim ss = new SemaphoreSlim(1);

    private List<LitePoi> _results { get; set; } = new List<LitePoi>();
    
    private async Task InputEvent()
    {
        await ss.WaitAsync();
        try
        {
            if (_inputTextForFocus.Value is not null)
            {
                _results = await PoiQueryService.QueryPoiFromString(_inputTextForFocus.Value);
            }
        }
        finally
        {
            ss.Release();
        }
    }
}