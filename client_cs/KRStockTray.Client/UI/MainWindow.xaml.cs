using KRStockTray.Client.Services;  // 해당 namespace에 선언된 타입들의 이름을생략해서 쓸 수 있게 한다는 뜻이다.
using KRStockTray.Client.ViewModels; // Quotes에 대한 정의가 있음.
using System;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Windows;
using System.Windows.Input;

namespace KRStockTray.Client.UI
{
    public partial class MainWindow : Window, INotifyPropertyChanged
    // “이 클래스는 XAML과 합쳐져 하나의 메인 창이 되며, WPF 창 기능을 상속하고, 내부 속성 변경을 UI에 알릴 수 있는 바인딩 대상이다.”
    // : Window — 이 클래스는 WPF의 “창(Window)”을 상속한다
    // INotifyPropertyChanged — 창 자체가 바인딩 대상. MainWindow 자체가 DataContext로 쓰이고, 그 안의 속성들이 UI에 바인딩된다
    // partial — XAML과 코드비하인드의 연결고리 : MainWindow.xaml과 MainWindow.xaml.cs 가 하나로 합쳐짐. XAML 기반 WPF에서는 필수
    {
        public event PropertyChangedEventHandler? PropertyChanged;
        private readonly SettingsService _settings;
        private readonly KrSymbolCacheService _krSymbols;
        private QuotePoller? _poller;  // “이 클래스 내부에서 관리하는 주가 조회 작업자가 하나 있는데, 아직 생성되지 않았을 수도 있다.”
                                       // using KRStockTray.Client.Services 으로 KRStockTray.Client.Services name
                                       // QuotePoller 클래스는 설계도 같은 것으로 KRStockTray.Client.Services에 정의 되어 있지만 
                                       // _poller는 그 정의에 따라 만들어진 것일뿐 나만 쓴다.
        private bool _hasShownOnce = false;

        // 위치/투명도 저장을 "즉시" 하지 말고, 디바운스해서 IO로 인한 지연/끊김을 없앤다.
        private readonly System.Windows.Threading.DispatcherTimer _saveDebounce;
        // DispatcherTimer는 WPF UI 스레드(Dispatcher)에서 동작하는 타이머

        protected void OnPropertyChanged(string? name = null)
        // protected - 이 클래스 + 상속받은 클래스만 호출 가능
        // void — 결과는 필요 없다
        // string? name - 변경된 속성의 이름
        // = nul - 인자를 안 주고 호출할 수 있다
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name)); // null이면“모든 속성이 바뀐 것처럼 취급해라”
        }

        public ObservableCollection<QuoteRowViewModel> Quotes { get; }
            = new ObservableCollection<QuoteRowViewModel>();
        // “UI에 바인딩되는 주가 행 목록을 제공하되, 외부에서는 목록 자체를 갈아끼우지 못하게 하고, 항목의 추가·삭제만 허용한다.”
        // 항목 추가/삭제가 UI에 자동 반영되는 컬렉션
        // { get; } — setter가 없다 (핵심 🔥) Quotes = new ObservableCollection<...>(); // ❌ 불가
        // Quotes[0]는 QuoteRowViewModel (삼성전자) 의 Code, Name, Price 등
        // 항목 추가, 삭제, 전부삭제, 값변경 가능, “컬렉션 자체를 갈아끼우는 것”만 금지


        public void AttachPoller(QuotePoller poller)
        {
            _poller = poller;
        }

        public MainWindow(SettingsService settings, KrSymbolCacheService krSymbols)
        {
            InitializeComponent();
            _settings = settings;
            _krSymbols = krSymbols;

            DataContext = this;

            _saveDebounce = new System.Windows.Threading.DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(400)
            };
            _saveDebounce.Tick += (_, __) =>
            {
                _saveDebounce.Stop();
                _settings.Save();
            };

            // 🔽 설정 변경 감시
            _settings.OnConfigChanged += (_, __) =>
            {
                Dispatcher.Invoke(() =>
                {
                    WindowOpacity = _settings.Config.WindowOpacity;
                    OnPropertyChanged(nameof(EffectiveOpacity));
                }, System.Windows.Threading.DispatcherPriority.Render);
            };

            // 🔁 저장된 UI 상태 복원
            WindowOpacity = _settings.Config.WindowOpacity;
            Left = _settings.Config.WindowLeft;
            Top = _settings.Config.WindowTop;

            // 이동 시 위치 저장
            LocationChanged += (_, __) => SaveWindowPosition(debounced: true);
        }

        /// <summary>
        /// App에서 QuotePoller 생성 후 연결해준다.
        /// (OnStartup에서 MainWindow를 먼저 만들기 때문에 poller를 나중에 주입)
        /// </summary>

        private double _windowOpacity = 0.85;
        public double WindowOpacity
        {
            get => _windowOpacity;
            set
            {
                if (_windowOpacity == value) return;
                _windowOpacity = value;
                OnPropertyChanged(nameof(WindowOpacity));
                OnPropertyChanged(nameof(EffectiveOpacity));

                // 💾 투명도 저장
                _settings.Config.WindowOpacity = value;
                DebouncedSave();
            }
        }

        private void RootBorder_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.LeftButton == MouseButtonState.Pressed)
                DragMove();
        }

        /// <summary>
        /// QuotePoller에서 전체 종목 리스트 갱신
        /// </summary>
        public void UpdateQuotes(IEnumerable<QuoteRowViewModel> rows)
        {
            Quotes.Clear();
            foreach (var r in rows)
                Quotes.Add(r);

            if (Quotes.Count > 0)
                Height = Quotes.Count * 26 + 12;

            if (!_hasShownOnce && Quotes.Count > 0)
            {
                _hasShownOnce = true;
                Opacity = 1;
                Show();
                Activate();
            }
        }

        /// <summary>
        /// X 버튼 클릭 시 종료되지 않게 숨김 처리
        /// </summary>
        protected override void OnClosing(CancelEventArgs e)
        {
            e.Cancel = true;

            SaveWindowPosition(debounced: false);
            _settings.Config.WindowOpacity = WindowOpacity;

            Hide();
        }

        private void RootBorder_MouseRightButtonUp(object sender, MouseButtonEventArgs e)
        {
            var dlg = new SettingsWindow(_settings, _krSymbols)
            {
                Owner = this
            };
            dlg.ShowDialog();
        }

        private void SaveWindowPosition(bool debounced)
        {
            _settings.Config.WindowLeft = Left;
            _settings.Config.WindowTop = Top;
            if (debounced) DebouncedSave();
            else _settings.Save();
        }

        private void DebouncedSave()
        {
            _saveDebounce.Stop();
            _saveDebounce.Start();
        }

        public double EffectiveOpacity
        {
            get
            {
                if (IsMouseOver)
                    return 1.0;                  // 마우스 오버 시 완전 투명
                return WindowOpacity;            // 평소 설정값
            }
        }

        private void RootBorder_MouseEnter(object sender, System.Windows.Input.MouseEventArgs e)
        {
            OnPropertyChanged(nameof(EffectiveOpacity));
        }

        private void RootBorder_MouseLeave(object sender, System.Windows.Input.MouseEventArgs e)
        {
            OnPropertyChanged(nameof(EffectiveOpacity));
        }
    }

}
