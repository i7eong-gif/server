namespace KRStockTray.Client.Models
{
    public sealed class QuoteModel
    {
        public string Market { get; init; } = "";
        public string Code { get; init; } = "";
        public double Price { get; init; }
        public double Delta { get; init; }
        public double Pct { get; init; }
        public long Volume { get; init; }
        public string PriceType { get; init; } = "";
    }
}
