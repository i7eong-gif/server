using System.Windows;
using System.Windows.Controls;

namespace KRStockTray.Client.UI
{
    public partial class AddByCodeWindow : Window
    {
        public string Market { get; private set; } = "US";
        public string Code { get; private set; } = "";

        public AddByCodeWindow()
        {
            InitializeComponent();
        }

        private void Add_Click(object sender, RoutedEventArgs e)
        {
            Market = ((ComboBoxItem)MarketBox.SelectedItem).Content.ToString()!;
            Code = CodeBox.Text.Trim().ToUpperInvariant();

            if (string.IsNullOrWhiteSpace(Code))
            {
                System.Windows.MessageBox.Show("코드를 입력하세요.");
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