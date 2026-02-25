using KRStockTray.Client.Services;
using System.Collections.Generic;
using System.Windows;

namespace KRStockTray.Client.UI
{
    public partial class SymbolSearchResultWindow : Window
    {
        public KrSymbol? Selected { get; private set; }

        public SymbolSearchResultWindow(List<KrSymbol> results)
        {
            InitializeComponent();
            List.ItemsSource = results;
        }

        private void Add_Click(object sender, RoutedEventArgs e)
        {
            Commit();
        }

        private void List_MouseDoubleClick(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            Commit();
        }

        private void Commit()
        {
            if (List.SelectedItem is not KrSymbol s)
                return;

            Selected = s;
            DialogResult = true;
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
        }
    }
}

