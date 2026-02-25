/*
 * SettingsService.cs
 *
 * 역할:
 * - 앱 전체 설정(AppConfig)의 단일 진실 소스(Single Source of Truth)
 * - 설정 로드/저장
 * - 설정 변경을 UI에 "즉시 알림"으로 전달
 *
 * 설계 원칙:
 * - UI는 Config를 직접 저장하지 않는다
 * - 저장(Save)과 반영(NotifyChanged)을 철저히 분리한다
 * - 설정 변경은 항상 SettingsService를 통해서만 이뤄진다
 */

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Text.Json;

namespace KRStockTray.Client.Services
{
    // =========================================================
    // AppConfig
    // =========================================================
    /*
     * AppConfig는 "직렬화 대상 데이터"만을 담는다.
     * - 로직 ❌
     * - 이벤트 ❌
     * - UI 의존성 ❌
     */
    public sealed class AppConfig
    {
        public string ServerUrl { get; set; } = "http://127.0.0.1:8000";
        // { get; set; } - 내부 필드 따로 안 만들고 컴파일러가 자동으로 만들어줌
        // get => _serverUrl;, set => _serverUrl = value;
        // get; set; -> 설정 창에서 변경 가능, JSON 설정 파일에서 덮어쓰기 가능
        public string? Serial { get; set; }

        public bool ShowOnStart { get; set; } = true;
        public bool AutoStart { get; set; } = false;

        // 사용자가 감시하는 종목 목록
        public ObservableCollection<SettingsService.WatchItem> WatchList { get; set; } = new ObservableCollection<SettingsService.WatchItem>()
        // “SettingsService에 정의된 WatchItem 객체들을 담는,
        // 추가·삭제가 UI에 자동 반영되는 공개 리스트 속성을 만들고,
        // 처음부터 비어 있는 상태로 초기화한다.”
        // ObservableCollection<T> -“항목이 추가/삭제되면 UI에게 자동으로 알려주는 리스트”
        // SettingsService.WatchItem -“SettingsService 안에 정의된 WatchItem 타입의 목록”
        // public — UI 바인딩을 위해 필수
        // { get; set; } - get → UI가 읽음, set → 교체 가능
        // = new ObservableCollection<...>() — 즉시 초기화 - “null 상태 없이 바로 사용 가능하게 만든다”
        {
            new SettingsService.WatchItem { Market = "KR", Code = "005930" }
        };

        // 폴링 / 회전 주기
        public int RotateSeconds { get; set; } = 10;
        public int RefreshSeconds { get; set; } = 5;
        public int PollIntervalSec { get; set; } = 5;

        // UI 상태 (위치/투명도)
        public double WindowOpacity { get; set; } = 0.85;
        public double WindowLeft { get; set; } = 100;
        public double WindowTop { get; set; } = 100;
    }

    // =========================================================
    // SettingsService
    // =========================================================
    /*
     * SettingsService는 AppConfig의 생명주기를 관리한다.
     *
     * 핵심 규칙:
     * - NotifyChanged() : UI 즉시 반영용
     * - Save()          : 디스크 저장용
     *
     * ❗ Save()는 절대 UI 이벤트를 발생시키지 않는다
     */
    public sealed class SettingsService
    {
        private readonly object _saveLock = new();
        // 여기서 object는 데이터가 아니라 도구. 오직 lock용
        // _saveLock - “저장(save) 작업을 보호하는 락”
        // 락 객체는 절대 public이면 안 됨
        // readonly — “_saveLock 변수가 가리키는 객체는 생성자 이후 절대 바뀌지 않는다". 재할당을 불가능하게 함.
        // = new(); - new object()와 완전히 동일.

        public AppConfig Config { get; private set; } = new AppConfig();
        // “설정 객체는 항상 존재하며, 외부에서는 읽기만 가능하고, 교체는 이 클래스만 할 수 있다.”
        // AppConfig 는 설정의 묶음.
        // public — 읽는 건 모두 허용
        // { get; private set; } - 누구나 읽기 가능 & 이 클래스 내부만 교체 가능
        // 설정은 SettingsService에서만 바꿀 수 있음.
        // = new AppConfig(); — 항상 null 아님 보장

        public event EventHandler? OnConfigChanged;
        // “이 객체는 설정이 바뀌었을 때,그 사실을 외부에게 알려주는 이벤트를 하나 가지고 있다.”
        // event — “구독만 가능, 호출은 내부만”
        // EventHandler - “무슨 설정이 바뀌었는지는 중요 없고, 어쨌든 설정이 바뀌었다” 라는 신호용
        // ? — 아직 구독자가 없을 수도 있음

        private readonly string _dir;
        private readonly string _path;

        public SettingsService() //SettingsService 객체가 만들어질 때 자동으로 한 번 실행.
                                 // var settings = new SettingsService(); 등의 형태일 때 실행됨.
        {
            _dir = Path.Combine(   // _dir = C:\Users\...\AppData\Roaming\KRStockTray
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                // 현재 사용자 전용 AppData 폴더 경로를 가져온다. 보통C:\Users\사용자이름\AppData\Roaming
                "KRStockTray"
            );
            _path = Path.Combine(_dir, "config.json");  // C:\Users\일준\AppData\Roaming\KRStockTray\config.json
        }

        // =====================================================
        // WatchItem
        // =====================================================
        /*
         * WatchItem은 UI 바인딩 대상이므로
         * INotifyPropertyChanged를 구현한다.
         */
        public sealed class WatchItem : INotifyPropertyChanged
        // class WatchItem - 감시 대상(종목) 하나를 표현하는 모델 객체
        // public — 어디서든 접근 가능
        // sealed — “상속 금지”: 성능상“빈번히 갱신되는 객체”에는 sealed가 아주 좋은 선택
        // INotifyPropertyChanged - 속성 값이 바뀌었음을 UI에게 알려주는 인터페이스
        {
            public event PropertyChangedEventHandler? PropertyChanged;
            // “이 객체는‘속성이 바뀌었음’을 알리는 이벤트를 가지고 있고, 외부(WPF UI 등)는 그 신호를 구독할 수 있다.
            // PropertyChanged - “속성이 바뀌었다”는 신호의 이름. WPF가 자동으로 알아듣는다.
            // event - 외부에서는 **구독(subscribe)**만 가능
            // ? — null 가능 표시
            // private이면 WPF가 못 본다.

            private bool _isEnabled = true;
            private string _market = "";
            private string _code = "";
            private string _name = "";

            public bool IsEnabled
            {
                get => _isEnabled;
                set
                {
                    if (_isEnabled == value) return;
                    _isEnabled = value;
                    OnChanged(nameof(IsEnabled));
                }
            }

            public string Market // KR or US
            {
                get => _market;
                set
                {
                    if (_market == value) return; // 값이 안 바뀌었으면 아무것도 하지 마라. 불필요한 UI 갱신 방지
                    _market = value;
                    OnChanged(nameof(Market)); // “Market 속성이 바뀌었다.”<TextBlock Text="{Binding Market}" />가 갱신 됨.
                    OnChanged(nameof(DisplayText)); // DisplayText는 독립 속성이 아니라
                                                    // Market, Code, Price에 “의존”하는 계산 결과.
                                                    //“DisplayText도 같이 다시 그려!”
                }
            }

            public string Code
            {
                get => _code;
                set
                {
                    if (_code == value) return;
                    _code = value;
                    OnChanged(nameof(Code));
                    OnChanged(nameof(DisplayText));
                }
            }

            public string Name
            {
                get => _name;
                set
                {
                    if (_name == value) return;
                    _name = value;
                    OnChanged(nameof(Name));
                    OnChanged(nameof(DisplayText));
                }
            }

            // 설정창/주가창 공통 표시 문자열
            public string DisplayText =>
                !string.IsNullOrEmpty(Name)  //“Name이 null도 아니고, 빈 문자열도 아니면”, 종목명 없는 케이스도 있기 때문
                    ? $"{Name} ({Code})"   // 조건 ? 참일 때 : 거짓일 때 - Name 있음 → "삼성전자 (005930)"
                    : Code;                // Name 없음 → "005930"

            private void OnChanged(string name)
            {
                PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
                // “이 객체(this)에서 name이라는 속성이 변경되었음을 듣고 있는 모든 UI에게 안전하게 알린다.”
                // new PropertyChangedEventArgs(name) — 뭐가 바뀌었나?
            }
        }

        // =====================================================
        // Load / Save
        // =====================================================

        /// <summary>
        /// 설정을 로드하거나 없으면 생성한다.
        /// UI 반영 이벤트는 반드시 발생시킨다.
        /// </summary>===========================
        public void LoadOrCreate()  // App.xaml.cs의 OnStartup() 직후 1번 사용
        // 애플리케이션 시작 시, App(Main)에서 단 한 번 호출되어 이후 모든 코드가 설정을 신뢰할 수 있게 만드는 초기화 메서드다.
        {
            Directory.CreateDirectory(_dir);  //지정한 경로의 디렉터리가 없으면 생성한다

            if (!File.Exists(_path))  // “없다면?”
            {
                Save();  // “기본 설정으로 최초 config.json을 만든다”
                NotifyChanged();
                return;
            }

            try  // try { ... } — 실패할 수 있는 구간을 묶는다  
            {
                string json = File.ReadAllText(_path);  // config.json 내용을 문자열로 통째로 읽는다
                var cfg = JsonSerializer.Deserialize<AppConfig>(json);  // JSON 문자열을 AppConfig 객체로 복원. 성공 → AppConfig 객체, 실패 -> 예외, 애매한 경우 → null
                if (cfg != null)                                        // 예외가 발생하면 가장 가까운 catch를 찾음
                    Config = cfg;              // 정상객체 ->  설정 교체              
            }
            catch  // 조용한 복구 전략
            {
                // 설정 파일 손상 시 기본값 유지  파일 손상 → 기본값으로 대체
            }

            NotifyChanged(); //
        }


        /// <summary>
        /// 설정을 디스크에 저장한다.
        /// ❗ UI 이벤트를 발생시키지 않는다
        /// </summary>
        public void Save()
        {
            Directory.CreateDirectory(_dir);

            var opt = new JsonSerializerOptions //JSON을 보기 좋게 줄 맞춰서 저장해라
            {
                WriteIndented = true // 줄 맞춰서
            };

            lock (_saveLock) // Config 상태를 “한 시점”으로 고정해서 저장. 없으면 직렬화 중간에 Config 값이 바뀔 수 있음
            {
                File.WriteAllText(     // File.WriteAllText(_path, ...) — _path 파일에 저장
                    _path,
                    JsonSerializer.Serialize(Config, opt)  // “Config의 현재 상태를 그대로 스냅샷으로 뜬다”
                );
            }
        }

        /// <summary>
        /// 설정 변경을 UI에 즉시 알린다.
        /// </summary>
        public void NotifyChanged()
        {
            OnConfigChanged?.Invoke(this, EventArgs.Empty);
        }
    }
}
