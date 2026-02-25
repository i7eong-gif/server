/*
 * SettingsWindow.xaml.cs
 *
 * 역할:
 * - 사용자가 WatchList 및 UI 옵션을 편집하는 설정 창
 *
 * 핵심 설계:
 * - UI 전용 ObservableCollection을 사용
 * - 변경 시 즉시 Config에 동기화
 * - 저장 버튼 개념 ❌ (즉시 반영 모델)
 */

using KRStockTray.Client.Services;
using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using static KRStockTray.Client.Services.SettingsService;

namespace KRStockTray.Client.UI
{
    public partial class SettingsWindow : Window
    {
        private readonly SettingsService _settings;
        private readonly KrSymbolCacheService _krSymbols;

        // WPF 전용 Point
        private System.Windows.Point _dragStartPoint;


        public SettingsWindow(SettingsService settings, KrSymbolCacheService krSymbols)
        {
            InitializeComponent();

            _settings = settings;
            _krSymbols = krSymbols;

            // 🔑 Config의 WatchList를 그대로 사용 (복사 ❌)
            DataContext = _settings.Config;
            WatchListView.ItemsSource = _settings.Config.WatchList;

            AlphaSlider.Value = _settings.Config.WindowOpacity;
            AlphaText.Text = $"{_settings.Config.WindowOpacity:0.00}";

            AutoStartCheck.IsChecked = AutoStartService.IsEnabled();
        }

        // ==================================================
        // 코드로 추가
        // ==================================================
        private void AddByCode_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new AddByCodeWindow { Owner = this };
            if (dlg.ShowDialog() != true)
                return;

            string name = "";

            // KR이면 종목명 조회
            if (dlg.Market == "KR")
            {
                var sym = _krSymbols.Symbols
                    .FirstOrDefault(s => s.Code == dlg.Code);

                if (sym != null)
                    name = sym.Name;
            }

            _settings.Config.WatchList.Add(new WatchItem
            {
                Market = dlg.Market,
                Code = dlg.Code,
                Name = name,
                IsEnabled = true
            });

            _settings.NotifyChanged();
        }

        // ==================================================
        // 종목명으로 추가 (KR)
        // ==================================================
        private void AddByNameKr_Click(object sender, RoutedEventArgs e)
        {
            var input = new SymbolSearchInputWindow
            {
                Owner = this
            };

            if (input.ShowDialog() != true)
                return;

            var results = _krSymbols.Search(input.Query);
            if (results.Count == 0)
            {
                System.Windows.MessageBox.Show("검색 결과가 없습니다.");
                return;
            }

            var pick = new SymbolSearchResultWindow(results)
            {
                Owner = this
            };

            if (pick.ShowDialog() == true && pick.Selected != null)
            {
                if (_settings.Config.WatchList.Any(w =>
                    w.Market == "KR" && w.Code == pick.Selected.Code))
                {
                    System.Windows.MessageBox.Show("이미 추가된 종목입니다.");
                    return;
                }

                _settings.Config.WatchList.Add(new WatchItem
                {
                    Market = "KR",
                    Code = pick.Selected.Code,
                    Name = pick.Selected.Name,
                    IsEnabled = true
                });

                _settings.NotifyChanged();
            }
        }

        // ==================================================
        // 삭제 / 활성 토글
        // ==================================================
        private void Remove_Click(object sender, RoutedEventArgs e)
        {
            if (WatchListView.SelectedItem is not WatchItem w)
                return;

            _settings.Config.WatchList.Remove(w);
            _settings.NotifyChanged();
        }

        private void Toggle_Click(object sender, RoutedEventArgs e)
        {
            if (WatchListView.SelectedItem is not WatchItem w)
                return;

            w.IsEnabled = !w.IsEnabled;
            _settings.NotifyChanged();
        }

        // ==================================================
        // 드래그 이동
        // ==================================================
        private void WatchList_PreviewMouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            _dragStartPoint = e.GetPosition(null);
        }

        private void WatchList_MouseMove(object sender, System.Windows.Input.MouseEventArgs e)
        {
            if (e.LeftButton != MouseButtonState.Pressed)
                return;

            var pos = e.GetPosition(null);
            if (Math.Abs(pos.X - _dragStartPoint.X) < SystemParameters.MinimumHorizontalDragDistance &&
                Math.Abs(pos.Y - _dragStartPoint.Y) < SystemParameters.MinimumVerticalDragDistance)
                return;

            if (WatchListView.SelectedItem == null)
                return;

            DragDrop.DoDragDrop(
                WatchListView,
                WatchListView.SelectedItem,
                System.Windows.DragDropEffects.Move);
        }

        private void WatchList_Drop(object sender, System.Windows.DragEventArgs e)
        {
            if (!e.Data.GetDataPresent(typeof(WatchItem)))
                return;

            var dropped = (WatchItem)e.Data.GetData(typeof(WatchItem))!;
            var container = FindParent<System.Windows.Controls.ListViewItem>(e.OriginalSource as DependencyObject);

            if (container?.DataContext is not WatchItem target || target == dropped)
                return;

            var list = _settings.Config.WatchList;

            int oldIndex = list.IndexOf(dropped);
            int newIndex = list.IndexOf(target);

            if (oldIndex < 0 || newIndex < 0)
                return;

            // ⭐ ObservableCollection 전용 이동
            list.Move(oldIndex, newIndex);

            WatchListView.SelectedItem = dropped;
            _settings.NotifyChanged();
        }

        // ==================================================
        // 투명도
        // ==================================================
        private void AlphaSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (AlphaText == null)
                return;

            _settings.Config.WindowOpacity = AlphaSlider.Value;
            AlphaText.Text = $"{AlphaSlider.Value:0.00}";
            _settings.NotifyChanged();
        }

        // ==================================================
        // 닫기
        // ==================================================
        private void Close_Click(object sender, RoutedEventArgs e)
        {
            Close();
        }

        // ==================================================
        // VisualTree Helper
        // ==================================================
        private static T? FindParent<T>(DependencyObject? obj) where T : DependencyObject
        {
            while (obj != null)
            {
                if (obj is T t)
                    return t;
                obj = VisualTreeHelper.GetParent(obj);
            }
            return null;
        }
    }
}