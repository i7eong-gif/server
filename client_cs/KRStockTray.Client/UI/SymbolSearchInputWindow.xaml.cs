using System.Windows;
using System.Windows.Input;

namespace KRStockTray.Client.UI
{
    public partial class SymbolSearchInputWindow : Window
    {
        public string Query { get; private set; } = "";

        public SymbolSearchInputWindow()
        {
            InitializeComponent();
            Loaded += (_, _) => QueryBox.Focus();
        }

        private void Search_Click(object sender, RoutedEventArgs e)
        {
            Commit();
        }

        private void QueryBox_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
        {
            if (e.Key == Key.Enter)
                Commit();
        }

        private void Commit()
        {
            Query = QueryBox.Text.Trim();
            if (string.IsNullOrWhiteSpace(Query))
            {
                System.Windows.MessageBox.Show("종목명을 입력하세요.");
                return;
            }
            DialogResult = true;
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
        }
    }
}
