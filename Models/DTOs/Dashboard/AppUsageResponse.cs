namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class AppUsageResponse
    {
        public string AppName { get; set; }
        public int DurationSeconds { get; set; }
        public double Percentage { get; set; }
        public int SessionCount { get; set; }
    }
}
