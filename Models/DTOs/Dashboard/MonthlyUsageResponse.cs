namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class MonthlyUsageResponse
    {
        public List<MonthlyEntry> Months { get; set; }
    }

    public class MonthlyEntry
    {
        public int Year { get; set; }
        public int Month { get; set; }
        public int DurationSeconds { get; set; }
        public int SessionCount { get; set; }
    }
}
