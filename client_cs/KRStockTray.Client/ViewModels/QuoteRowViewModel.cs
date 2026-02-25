using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace KRStockTray.Client.ViewModels
{
    public class QuoteRowViewModel : INotifyPropertyChanged
    {
        public event PropertyChangedEventHandler? PropertyChanged;
        private void OnPropertyChanged([CallerMemberName] string? name = null)
            => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

        public string Market { get; private set; } = "";
        public string Code { get; private set; } = "";
        public string Name { get; private set; } = "";
        public double Price { get; private set; }
        public double Delta { get; private set; }
        public double Pct { get; private set; }
        public long Volume { get; private set; }

        // 🇰🇷 KR: 종목명 / 🇺🇸 US: 티커
        public string DisplaySymbol =>
            Market == "KR" ? Name : Code;

        // 가격 포맷
        public string PriceText =>
            Market == "US" ? Price.ToString("N2") : Price.ToString("N0");

        // 등락
        public string DeltaText
        {
            get
            {
                var fmt = Market == "US" ? "N2" : "N0";
                return Delta > 0 ? $"+{Delta.ToString(fmt)}" :
                       Delta < 0 ? $"{Delta.ToString(fmt)}" :
                       "0";
            }
        }

        public string PctText =>
            Pct > 0 ? $"+{Pct:0.00}%" :
            Pct < 0 ? $"{Pct:0.00}%" :
            "0.00%";

        public string TrayText
        {
            get
            {
                var name = Name.Length > 20 ? Name[..20] + "…" : Name;
                var line1 = $"[{Code}] {name}";
                var line2 = $"{Price:N0} {DeltaText}";
                var text = $"{line1}\n{line2}";
                return text.Length > 63 ? text[..63] : text;
            }
        }

        // 기존 XAML 호환
        public string DiffText => DeltaText;
        public System.Windows.Media.Brush DiffColor => Color;

        public System.Windows.Media.Brush Color =>
            Delta > 0 ? System.Windows.Media.Brushes.OrangeRed :
            Delta < 0 ? System.Windows.Media.Brushes.DodgerBlue :
            System.Windows.Media.Brushes.Gray;

        // 🔁 서버 데이터 반영은 반드시 여기로
        public void Update(
            string market,
            string code,
            string name,
            double price,
            double delta,
            double pct,
            long volume)
        {
            Market = market;
            Code = code;
            Name = string.IsNullOrEmpty(name) ? code : name;
            Price = price;
            Delta = delta;
            Pct = pct;
            Volume = volume;

            // 🔔 계산/표시용 프로퍼티 전부 알림
            OnPropertyChanged(nameof(DisplaySymbol));
            OnPropertyChanged(nameof(PriceText));
            OnPropertyChanged(nameof(DeltaText));
            OnPropertyChanged(nameof(PctText));
            OnPropertyChanged(nameof(Color));
            OnPropertyChanged(nameof(DiffText));
            OnPropertyChanged(nameof(DiffColor));
        }
    }
}