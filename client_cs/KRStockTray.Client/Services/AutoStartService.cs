using Microsoft.Win32;
using System;
using System.Diagnostics;

namespace KRStockTray.Client.Services
{
    public static class AutoStartService
    {
        private const string RunKey =
            @"Software\Microsoft\Windows\CurrentVersion\Run";

        private const string AppName = "KRStockTray";

        /// <summary>
        /// 자동 실행 등록
        /// </summary>
        public static void Enable()
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, true)
                ?? Registry.CurrentUser.CreateSubKey(RunKey);

            string exePath = GetExePath();
            key.SetValue(AppName, exePath);
        }

        /// <summary>
        /// 자동 실행 해제
        /// </summary>
        public static void Disable()
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, true);
            key?.DeleteValue(AppName, false);
        }

        /// <summary>
        /// 현재 자동 실행 상태
        /// </summary>
        public static bool IsEnabled()
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey);
            return key?.GetValue(AppName) != null;
        }

        /// <summary>
        /// 실행 파일 경로 (exe / dotnet run 모두 대응)
        /// </summary>
        private static string GetExePath()
        {
            return Process.GetCurrentProcess().MainModule!.FileName!;
        }
    }
}
