namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class HourlyUsageResponse
    {
        public List<HourlyEntry> Hours { get; set; }
    }

    public class HourlyEntry
    {
        public int Hour { get; set; }
        public int DurationSeconds { get; set; }
        public int SessionCount { get; set; }
    }
}
