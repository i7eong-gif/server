using KRStockTray.Client.Models;
using System.IO;
using System.Text.Json;

namespace KRStockTray.Client.Services;

public static class SymbolLoader
{
    private static string AppDir =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "KRStockTray"
        );

    public static List<KrSymbol> LoadKrSymbols()
    {
        Directory.CreateDirectory(AppDir);

        string dst = Path.Combine(AppDir, "symbols_kr.json");
        string src = Path.Combine(AppContext.BaseDirectory, "symbols_kr.json");

        if (!File.Exists(dst))
            File.Copy(src, dst);

        var json = File.ReadAllText(dst);
        return JsonSerializer.Deserialize<List<KrSymbol>>(json)!;
    }
}
