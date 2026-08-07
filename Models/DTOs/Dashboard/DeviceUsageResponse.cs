namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class DeviceUsageResponse
    {
        public Guid DeviceId { get; set; }
        public string DeviceName { get; set; } = string.Empty;
        public string Platform { get; set; } = string.Empty;
        public bool IsActive { get; set; }
        public DateTime? LastSyncAt { get; set; }
        public int DurationSeconds { get; set; }
        public double Percentage { get; set; }
        public int SessionCount { get; set; }
    }
}
