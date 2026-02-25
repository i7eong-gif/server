using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using KRStockTray.Client.Services;

namespace KRStockTray.Client.Api
{
    public sealed class StockApiClient
    {
        private readonly HttpClient _http;
        public HttpClient Http => _http;
        private readonly string _device;
        private string? _serial;

        public StockApiClient(string baseUrl, string? serial)
        {
            _device = DeviceService.GetDeviceHash();
            _serial = serial;

            _http = new HttpClient
            {
                BaseAddress = new Uri(baseUrl.TrimEnd('/')),
                Timeout = TimeSpan.FromSeconds(20)
            };
        }

        private void ApplyHeaders(bool includeSerial)
        {
            _http.DefaultRequestHeaders.Clear();
            _http.DefaultRequestHeaders.Add("X-Device", _device);
            if (includeSerial && !string.IsNullOrWhiteSpace(_serial))
                _http.DefaultRequestHeaders.Add("X-Serial", _serial);
        }

        public void SetSerial(string serial) => _serial = serial;

        public async Task<TrialResponse> ActivateTrialAsync()
        {
            ApplyHeaders(includeSerial: false);

            var resp = await _http.PostAsync("/activate/trial", null);
            resp.EnsureSuccessStatusCode();

            var data = await resp.Content.ReadFromJsonAsync<TrialResponse>();

            if (data == null || !data.Ok || data.Data == null ||
                string.IsNullOrWhiteSpace(data.Data.Serial))
            {
                throw new InvalidOperationException("Trial activation failed");
            }

            return data;
        }

        public async Task<QuoteResponse> QuoteAsync(string market, string code, CancellationToken ct = default)
        {
            ApplyHeaders(includeSerial: true);

            HttpResponseMessage resp;
            try
            {
                resp = await _http.GetAsync($"quote/{market}/{code}", ct);
            }
            catch
            {
                // 1회 재시도
                await Task.Delay(300, ct);
                resp = await _http.GetAsync($"quote/{market}/{code}", ct);
            }
            resp.EnsureSuccessStatusCode();

            var data = await resp.Content.ReadFromJsonAsync<QuoteResponse>(cancellationToken: ct);
            if (data == null || !data.Ok || data.Data == null)
                throw new InvalidOperationException("Quote response invalid");

            return data;
        }
    }
}
