namespace CrossDeviceTracker.Api.Services
{
    public class TimeAnalyticsService : ITimeAnalyticsService
    {
        public List<Interval> MergeIntervals(List<Interval> intervals)
        {
            if (intervals == null || intervals.Count == 0)
            {
                return new List<Interval>();
            }

            // Sort by start time
            var sorted = intervals.OrderBy(i => i.Start).ToList();

            var merged = new List<Interval>();
            var current = sorted[0];

            for (int i = 1; i < sorted.Count; i++)
            {
                var next = sorted[i];

                // Check if intervals overlap
                if (next.Start <= current.End)
                {
                    // Merge: extend current end if next ends later
                    current.End = current.End > next.End ? current.End : next.End;
                }
                else
                {
                    // No overlap, add current and start new
                    merged.Add(current);
                    current = next;
                }
            }

            merged.Add(current);
            return merged;
        }

        public int CalculateAttentionTime(List<Interval> intervals)
        {
            var merged = MergeIntervals(intervals);
            return merged.Sum(i => (int)(i.End - i.Start).TotalSeconds);
        }
    }
}
