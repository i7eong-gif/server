using System.Security.Cryptography;
using System.Text;

namespace KRStockTray.Client.Services
{
    public static class DeviceService
    {
        public static string GetDeviceHash()
        {
            // 너무 민감하지 않으면서도 안정적인 해시
            string raw = $"{Environment.MachineName}|{Environment.UserName}";
            using var sha = SHA256.Create();
            return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(raw)));
        }
    }
}
