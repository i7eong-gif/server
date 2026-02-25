using System.Text.Json.Serialization;

namespace KRStockTray.Client.Api
{
    public sealed class QuoteResponse
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("data")]
        public QuoteData? Data { get; set; }

        [JsonPropertyName("notice")]
        public Notice? Notice { get; set; }
    }

    public sealed class QuoteData
    {
        [JsonPropertyName("market")]
        public string Market { get; set; } = "";

        [JsonPropertyName("code")]
        public string Code { get; set; } = "";

        [JsonPropertyName("name")]
        public string? Name { get; init; }

        [JsonPropertyName("price")]
        public double Price { get; set; }

        [JsonPropertyName("ref_price")]
        public double RefPrice { get; set; }

        [JsonPropertyName("delta")]
        public double Delta { get; set; }

        [JsonPropertyName("pct")]
        public double Pct { get; set; }

        [JsonPropertyName("price_type")]
        public string PriceType { get; set; } = ""; // INTRADAY / CLOSE

        [JsonPropertyName("volume")]
        public long Volume { get; set; }
    }

    public sealed class Notice
    {
        [JsonPropertyName("type")]
        public string Type { get; set; } = "";

        [JsonPropertyName("days_left")]
        public int DaysLeft { get; set; }
    }

    public sealed class TrialResponse
    {
        [JsonPropertyName("ok")]
        public bool Ok { get; set; }

        [JsonPropertyName("data")]
        public TrialData? Data { get; set; }
    }

    public sealed class TrialData
    {
        [JsonPropertyName("serial")]
        public string Serial { get; set; } = "";

        // 서버 구현에 따라 "expires_at" 형태가 보통이라 가정
        [JsonPropertyName("expires_at")]
        public string? ExpiresAt { get; set; }
    }
}
