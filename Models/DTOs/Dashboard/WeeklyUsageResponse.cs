namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class WeeklyUsageResponse
    {
        public List<WeeklyEntry> Weeks { get; set; }
    }

    public class WeeklyEntry
    {
        public DateTime WeekStart { get; set; }
        public DateTime WeekEnd { get; set; }
        public int DurationSeconds { get; set; }
        public int SessionCount { get; set; }
    }
}
