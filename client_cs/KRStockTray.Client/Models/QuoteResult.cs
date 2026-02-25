namespace KRStockTray.Client.Models;

public sealed record QuoteResult(
    string Code,
    string Name,
    double Price,
    double Pct,
    long Volume,
    DateTime Time,
    string Source   // "YAHOO"
);
