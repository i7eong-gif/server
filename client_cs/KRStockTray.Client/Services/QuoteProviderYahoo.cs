using System.Net.Http;
using System.Text.Json;
using KRStockTray.Client.Models;

namespace KRStockTray.Client.Services;

public sealed class QuoteProviderYahoo
{
    private readonly HttpClient _http = new HttpClient();
    private readonly Dictionary<string, KrSymbol> _symbols;

    public QuoteProviderYahoo(IEnumerable<KrSymbol> symbols)
    {
        _symbols = symbols.ToDictionary(s => s.Code);
    }

    public QuoteResult? GetQuote(string code)
    {
        if (!_symbols.TryGetValue(code, out var sym))
            return null;

        try
        {
            string url =
                $"https://query1.finance.yahoo.com/v8/finance/chart/{sym.Yahoo}" +
                "?interval=1m&range=1d";

            var json = _http.GetStringAsync(url).Result;

            using var doc = JsonDocument.Parse(json);
            var meta = doc.RootElement
                .GetProperty("chart")
                .GetProperty("result")[0]
                .GetProperty("meta");

            double price = meta.GetProperty("regularMarketPrice").GetDouble();
            double prev = meta.GetProperty("previousClose").GetDouble();
            long vol = meta.TryGetProperty("regularMarketVolume", out var v)
                ? v.GetInt64()
                : 0;

            double pct = prev > 0 ? (price - prev) / prev * 100 : 0;

            return new QuoteResult(
                sym.Code,
                sym.Name,
                price,
                pct,
                vol,
                DateTime.Now,
                "YAHOO"
            );
        }
        catch
        {
            return null;
        }
    }
}

