namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class DashboardSummaryResponse
    {
        public TodayScreenTime Today { get; set; }
        public YesterdayScreenTime Yesterday { get; set; }
        public ThisWeekScreenTime ThisWeek { get; set; }
        public ThisMonthScreenTime ThisMonth { get; set; }
        public int DeviceCount { get; set; }
        public int AppCount { get; set; }
        public MostUsedApp MostUsedApp { get; set; }
    }

    public class TodayScreenTime
    {
        public int TotalScreenTimeSeconds { get; set; }
        public int TotalDeviceUsageSeconds { get; set; }
        public int OverlapTimeSeconds { get; set; }
        public int SessionCount { get; set; }
    }

    public class YesterdayScreenTime
    {
        public int TotalScreenTimeSeconds { get; set; }
        public int SessionCount { get; set; }
    }

    public class ThisWeekScreenTime
    {
        public int TotalScreenTimeSeconds { get; set; }
        public int SessionCount { get; set; }
    }

    public class ThisMonthScreenTime
    {
        public int TotalScreenTimeSeconds { get; set; }
        public int SessionCount { get; set; }
    }

    public class MostUsedApp
    {
        public string AppName { get; set; }
        public int DurationSeconds { get; set; }
    }
}
