namespace CrossDeviceTracker.Api.Models.DTOs.Dashboard
{
    public class TimelineResponse
    {
        public List<TimelineEntry> Entries { get; set; }
    }

    public class TimelineEntry
    {
        public DateTime Start { get; set; }
        public DateTime End { get; set; }
        public string App { get; set; }
        public string Device { get; set; }
        public string Platform { get; set; }
        public int DurationSeconds { get; set; }
    }
}
