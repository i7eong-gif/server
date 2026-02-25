using System;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Threading;
using System.Windows;
using WinForms = System.Windows.Forms;
using KRStockTray.Client.Services;
using KRStockTray.Client.UI;
using KRStockTray.Client.Api;

namespace KRStockTray.Client  // Class의 상위 개념.“KRStockTray 프로젝트의 클라이언트 영역 코드입니다”
{
    public partial class App : System.Windows.Application
    {
        private WinForms.NotifyIcon? _tray;
        private MainWindow? _mainWindow;

        private SettingsService? _settings;
        private QuotePoller? _poller;

        private static Mutex? _mutex;

        private bool _krSymbolsReady = false;
        private KrSymbolCacheService _krSymbols = null!;

        protected override async void OnStartup(StartupEventArgs e)
        {
            // ===============================
            // 0) 단일 실행 보장
            // ===============================
            _mutex = new Mutex(true, "KRStockTray.SingleInstance", out bool created);
            if (!created)
            {
                System.Windows.MessageBox.Show(
                    "KRStockTray가 이미 실행 중입니다.",
                    "KRStockTray",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                Shutdown();
                return;
            }

            base.OnStartup(e);
            ShutdownMode = ShutdownMode.OnExplicitShutdown;

            // ===============================
            // 1) 설정 로드
            // ===============================
            _settings = new SettingsService();
            _settings.LoadOrCreate();

            // 자동 실행 설정
            if (_settings.Config.AutoStart)
                AutoStartService.Enable();
            else
                AutoStartService.Disable();

            // ===============================
            // 2) KR 종목 캐시 초기화
            // ===============================
            string baseDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "KRStockTray"
            );

            var api = new StockApiClient(
                _settings.Config.ServerUrl,
                _settings.Config.Serial
            );

            _krSymbols = new KrSymbolCacheService(baseDir);
            try
            {
                await _krSymbols.InitializeAsync(api);
                _krSymbolsReady = true;
            }
            catch (Exception ex)
            {
                System.Windows.MessageBox.Show(
                    $"종목 목록 초기화 실패:\n{ex.Message}",
                    "KRStockTray",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
            }

            // ===============================
            // 3) 트레이 아이콘
            // ===============================
            _tray = new WinForms.NotifyIcon
            {
                Icon = LoadTrayIcon(),
                Visible = true,
                Text = "KRStockTray"
            };

            _tray.DoubleClick += (_, _) => Dispatcher.Invoke(ToggleMainWindow);

            var menu = new WinForms.ContextMenuStrip();
            menu.Items.Add("창 보이기/숨기기", null, (_, _) => Dispatcher.Invoke(ToggleMainWindow));
            menu.Items.Add("설정", null, (_, _) => Dispatcher.Invoke(OpenSettings));
            menu.Items.Add("-");
            menu.Items.Add("종료", null, (_, _) => Dispatcher.Invoke(ExitApp));
            _tray.ContextMenuStrip = menu;

            // ===============================
            // 4) 메인 윈도우 생성 (숨김)
            // ===============================
            _mainWindow = new MainWindow(_settings, _krSymbols);
            _mainWindow.Opacity = 0;
            _mainWindow.Hide();

            // ===============================
            // 5) ⭐ QuotePoller 생성 & 시작 (핵심)
            // ===============================
            _poller = new QuotePoller(
                _settings,
                _tray!,
                _mainWindow!
            );

            await _poller.InitializeAsync();
            _poller.Start();

            _mainWindow.AttachPoller(_poller);

            // ===============================
            // 6) 시작 시 창 표시 옵션
            // ===============================
            if (_settings.Config.ShowOnStart)
            {
                Dispatcher.Invoke(() => ShowMainWindow());
            }
        }

        // ===============================
        // 창 표시/숨김
        // ===============================
        private void ToggleMainWindow()
        {
            if (_mainWindow == null) return;

            if (_mainWindow.IsVisible)
                _mainWindow.Hide();
            else
                ShowMainWindow();
        }

        private void ShowMainWindow()
        {
            if (_mainWindow == null) return;

            _mainWindow.Opacity = _settings?.Config.WindowOpacity ?? 0.85;

            if (!_mainWindow.IsVisible)
                _mainWindow.Show();

            if (_mainWindow.WindowState == WindowState.Minimized)
                _mainWindow.WindowState = WindowState.Normal;

            _mainWindow.Activate();
        }

        // ===============================
        // 설정 창
        // ===============================
        private void OpenSettings()
        {
            if (_settings == null || !_krSymbolsReady)
            {
                System.Windows.MessageBox.Show(
                    "아직 초기화 중입니다. 잠시 후 다시 시도해주세요.",
                    "KRStockTray",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                return;
            }

            if (_poller == null)
            {
                System.Windows.MessageBox.Show(
                    "시세 서비스가 아직 준비되지 않았습니다.\n잠시 후 다시 시도해주세요.",
                    "KRStockTray",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                return;
            }

            var win = new SettingsWindow(_settings, _krSymbols)
            {
                Owner = _mainWindow
            };

            win.ShowDialog();
        }

        // ===============================
        // 종료
        // ===============================
        private async void ExitApp()
        {
            try { if (_poller != null) await _poller.StopAsync(); } catch { }
            try { _tray?.Dispose(); } catch { }

            Shutdown();
        }

        private Icon LoadTrayIcon()
        {
            var asm = Assembly.GetExecutingAssembly();

            // 🔑 Embedded Resource 이름
            const string resName = "KRStockTray.Client.Assets.tray.ico";

            using var stream = asm.GetManifestResourceStream(resName);
            if (stream == null)
                throw new InvalidOperationException("Tray icon resource not found.");

            return new Icon(stream);
        }
    }
}




