namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class DailyUsageResponse
    {
        public List<DailyEntry> Days { get; set; }
    }

    public class DailyEntry
    {
        public DateTime Date { get; set; }
        public int DurationSeconds { get; set; }
        public int SessionCount { get; set; }
    }
}
