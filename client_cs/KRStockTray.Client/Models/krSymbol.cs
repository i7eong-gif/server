namespace KRStockTray.Client.Models;

public sealed class KrSymbol
{
    public string Code { get; init; } = "";
    public string Name { get; init; } = "";
    public string Market { get; init; } = "";   // KOSPI / KOSDAQ / KR
    public string Type { get; init; } = "";     // STOCK / ETF
    public string Yahoo { get; init; } = "";    // 005930.KS
}
