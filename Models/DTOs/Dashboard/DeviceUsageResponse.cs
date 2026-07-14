namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class DeviceUsageResponse
    {
        public string DeviceName { get; set; }
        public string Platform { get; set; }
        public int DurationSeconds { get; set; }
        public double Percentage { get; set; }
        public int SessionCount { get; set; }
    }
}
