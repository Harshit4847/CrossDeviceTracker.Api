namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class DeviceUsageSummaryResponse
    {
        public int ActiveCount { get; set; }
        public List<DeviceUsageResponse> Devices { get; set; } = new();
    }
}
