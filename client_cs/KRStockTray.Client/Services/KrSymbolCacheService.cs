using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading.Tasks;
using KRStockTray.Client.Api;

namespace KRStockTray.Client.Services
{
    public sealed class KrSymbol
    {
        public string Code { get; set; } = "";
        public string Name { get; set; } = "";
        public string Market { get; set; } = "KRX"; // KRX / ETF
    }

    public sealed class KrSymbolCacheService
    {
        private readonly string _filePath;
        private readonly TimeSpan _ttl = TimeSpan.FromDays(1);
        private List<KrSymbol> _symbols = new();

        public IReadOnlyList<KrSymbol> Symbols => _symbols;

        public KrSymbolCacheService(string baseDir)
        {
            Directory.CreateDirectory(baseDir);
            _filePath = Path.Combine(baseDir, "symbols_kr.json");
        }

        public async Task InitializeAsync(StockApiClient api)
        {
            if (File.Exists(_filePath) && !IsExpired())
            {
                Load();
                return;
            }

            await FetchFromServerAsync(api);
        }

        private bool IsExpired()
        {
            var age = DateTime.Now - File.GetLastWriteTime(_filePath);
            return age > _ttl;
        }

        private void Load()
        {
            var json = File.ReadAllText(_filePath);
            _symbols = JsonSerializer.Deserialize<List<KrSymbol>>(json)!;
        }

        public List<KrSymbol> Search(string query)
        {
            if (string.IsNullOrWhiteSpace(query))
                return new List<KrSymbol>();

            query = query.Trim();

            return _symbols
                .Where(s =>
                    s.Name.Contains(query, StringComparison.OrdinalIgnoreCase) ||
                    s.Code.Contains(query, StringComparison.OrdinalIgnoreCase))
                .OrderBy(s => s.Name)
                .Take(100)   // 너무 많아지는 것 방지
                .ToList();
        }

        private async Task FetchFromServerAsync(StockApiClient api)
        {
            var resp = await api.Http.GetAsync("/symbols/KR/all");
            resp.EnsureSuccessStatusCode();

            using var stream = await resp.Content.ReadAsStreamAsync();
            using var doc = await JsonDocument.ParseAsync(stream);

            var data = doc.RootElement.GetProperty("data");
            var list = new List<KrSymbol>();

            foreach (var x in data.EnumerateArray())
            {
                list.Add(new KrSymbol
                {
                    Code = x.GetProperty("code").GetString()!,
                    Name = x.GetProperty("name").GetString()!,
                    Market = x.GetProperty("market").GetString()!
                });
            }

            _symbols = list;

            var json = JsonSerializer.Serialize(list);
            File.WriteAllText(_filePath, json);
        }
    }
}
