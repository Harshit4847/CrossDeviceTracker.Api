namespace CrossDeviceTracker.Api.Services
{
    public interface ITimeAnalyticsService
    {
        List<Interval> MergeIntervals(List<Interval> intervals);
        int CalculateAttentionTime(List<Interval> intervals);
    }

    public class Interval
    {
        public DateTime Start { get; set; }
        public DateTime End { get; set; }
    }
}
