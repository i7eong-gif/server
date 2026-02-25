using KRStockTray.Client.Api;
using KRStockTray.Client.Models;
using KRStockTray.Client.ViewModels;
using KRStockTray.Client.UI;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using WinForms = System.Windows.Forms;

namespace KRStockTray.Client.Services
{
    /// <summary>
    /// 서버에서 주가를 주기적으로 조회하여
    /// - MainWindow에는 전체 종목 표를 표시하고
    /// - Tray에는 순환 요약 텍스트를 표시한다
    /// </summary>
    public class QuotePoller
    {
        private readonly SettingsService _settings;
        private readonly WinForms.NotifyIcon _tray;
        private readonly MainWindow _window;

        private StockApiClient? _api;

        // 실행 제어
        private CancellationTokenSource? _cts;
        private Task? _loopTask;

        // 트레이 순환 인덱스 (기존 _watchIndex 유지)
        private int _watchIndex = 0;

        // 풍선 중복 방지
        private DateTime _lastBalloonAt = DateTime.MinValue;

        public QuotePoller(
            SettingsService settings,
            WinForms.NotifyIcon tray,
            MainWindow window)
        {
            _settings = settings;
            _tray = tray;
            _window = window;
        }

        /// <summary>
        /// 앱 시작 시 1회 초기화
        /// </summary>
        public async Task InitializeAsync()
        {
            // 0) API 클라이언트 생성 (필수)
            _api = new StockApiClient(
                _settings.Config.ServerUrl,
                _settings.Config.Serial
            );

            // 1) Serial 이미 있으면 그대로 사용
            if (!string.IsNullOrWhiteSpace(_settings.Config.Serial))
            {
                _api.SetSerial(_settings.Config.Serial!);
                return;
            }

            // 2) Trial 자동 발급
            var trial = await _api.ActivateTrialAsync();
            _settings.Config.Serial = trial.Data!.Serial;
            _settings.Save();

            _api.SetSerial(trial.Data.Serial);

            Balloon("체험판 시작", "체험판 시리얼이 자동 발급되었습니다.");
        }

        /// <summary>
        /// 폴링 시작
        /// </summary>
        public void Start()
        {
            if (_cts != null) return;

            _cts = new CancellationTokenSource();
            _loopTask = Task.Run(() => LoopAsync(_cts.Token));
        }

        /// <summary>
        /// 폴링 중지 (종료용)
        /// </summary>
        public async Task StopAsync()
        {
            if (_cts == null) return;

            try { _cts.Cancel(); } catch { }

            try
            {
                if (_loopTask != null)
                    await _loopTask;
            }
            catch { }

            try { _cts.Dispose(); } catch { }

            _cts = null;
            _loopTask = null;
        }

        /// <summary>
        /// 메인 루프 (절대 죽지 않게 설계)
        /// </summary>
        private async Task LoopAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    await FetchOnceAsync(ct);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Balloon("시세 오류", ex.Message);
                }

                int sec = _settings.Config.RefreshSeconds;
                if (sec < 3) sec = 3;

                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(sec), ct);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }

        /// <summary>
        /// 한 번의 전체 갱신
        /// - enabled 종목 전체 조회
        /// - MainWindow 표 갱신
        /// - Tray는 1종목만 순환 표시
        /// </summary>
        private async Task FetchOnceAsync(CancellationToken ct)
        {
            if (_api == null) return;

            var watches = _settings.Config.WatchList
                .Where(w => w.IsEnabled)
                .ToList();

            if (watches.Count == 0)
                return;

            var rows = new List<QuoteRowViewModel>();

            foreach (var w in watches)
            {
                ct.ThrowIfCancellationRequested();

                try
                {
                    var res = await _api.QuoteAsync(w.Market, w.Code);
                    if (!res.Ok || res.Data == null)
                        continue;

                    var q = res.Data;

                    var vm = new QuoteRowViewModel();
                    vm.Update(
                        q.Market,
                        q.Code,
                        q.Name ?? w.Code,
                        q.Price,
                        q.Delta,
                        q.Pct,
                        q.Volume
                    );

                    rows.Add(vm);
                }
                catch
                {
                    // 개별 실패 무시
                }
            }

            _window.Dispatcher.Invoke(() =>
            {
                _window.UpdateQuotes(rows);
            });

            UpdateTrayText(rows);
        }

        /// <summary>
        /// Tray 텍스트 순환 표시
        /// </summary>
        private void UpdateTrayText(List<QuoteRowViewModel> rows)
        {
            if (rows.Count == 0) return;

            if (_watchIndex >= rows.Count)
                _watchIndex = 0;

            var q = rows[_watchIndex];
            var text = q.TrayText;

            try { _tray.Text = text; } catch { }

            if (text.Length > 63)
                text = text.Substring(0, 63);

            try { _tray.Text = text; } catch { }

            _watchIndex++;
        }

        public async Task RefreshNowAsync()
        {
            if (_cts == null || _api == null)
                return;

            try
            {
                await FetchOnceAsync(_cts.Token);
            }
            catch
            {
                // 즉시 갱신 실패는 무시
            }
        }

        private void Balloon(string title, string message)
        {
            if ((DateTime.Now - _lastBalloonAt).TotalSeconds < 5)
                return;

            _lastBalloonAt = DateTime.Now;

            try
            {
                _tray.BalloonTipTitle = title;
                _tray.BalloonTipText = message;
                _tray.ShowBalloonTip(4000);
            }
            catch { }
        }
    }
}
