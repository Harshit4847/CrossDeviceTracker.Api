using CrossDeviceTracker.Api.Services;
using Xunit;

namespace CrossDeviceTracker.Api.Tests.Services
{
    public class TimeAnalyticsServiceTests
    {
        private readonly TimeAnalyticsService _service;

        public TimeAnalyticsServiceTests()
        {
            _service = new TimeAnalyticsService();
        }

        [Fact]
        public void MergeIntervals_TripleOverlap_ShouldMergeCorrectly()
        {
            // Arrange
            // Desktop: 10:00 - 11:00 (60 min)
            // Android: 10:15 - 10:45 (30 min)
            // Tablet: 10:20 - 10:40 (20 min)
            // Raw: 60 + 30 + 20 = 110 min
            // Expected Merged: 10:00 - 11:00 = 60 min
            // Expected Overlap: 110 - 60 = 50 min

            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(11) },
                new Interval { Start = baseDate.AddHours(10).AddMinutes(15), End = baseDate.AddHours(10).AddMinutes(45) },
                new Interval { Start = baseDate.AddHours(10).AddMinutes(20), End = baseDate.AddHours(10).AddMinutes(40) }
            };

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Single(merged);
            Assert.Equal(baseDate.AddHours(10), merged[0].Start);
            Assert.Equal(baseDate.AddHours(11), merged[0].End);
            Assert.Equal(60 * 60, (int)(merged[0].End - merged[0].Start).TotalSeconds);
        }

        [Fact]
        public void MergeIntervals_DoubleOverlap_ShouldMergeCorrectly()
        {
            // Arrange
            // Desktop: 10:00 - 11:00 (60 min)
            // Android: 10:30 - 11:30 (60 min)
            // Raw: 60 + 60 = 120 min
            // Expected Merged: 10:00 - 11:30 = 90 min
            // Expected Overlap: 120 - 90 = 30 min

            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(11) },
                new Interval { Start = baseDate.AddHours(10).AddMinutes(30), End = baseDate.AddHours(11).AddMinutes(30) }
            };

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Single(merged);
            Assert.Equal(baseDate.AddHours(10), merged[0].Start);
            Assert.Equal(baseDate.AddHours(11).AddMinutes(30), merged[0].End);
            Assert.Equal(90 * 60, (int)(merged[0].End - merged[0].Start).TotalSeconds);
        }

        [Fact]
        public void MergeIntervals_NonOverlapping_ShouldNotMerge()
        {
            // Arrange
            // Desktop: 10:00 - 11:00 (60 min)
            // Android: 12:00 - 13:00 (60 min)
            // Raw: 60 + 60 = 120 min
            // Expected Merged: 120 min (no overlap)

            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(11) },
                new Interval { Start = baseDate.AddHours(12), End = baseDate.AddHours(13) }
            };

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Equal(2, merged.Count);
            Assert.Equal(baseDate.AddHours(10), merged[0].Start);
            Assert.Equal(baseDate.AddHours(11), merged[0].End);
            Assert.Equal(baseDate.AddHours(12), merged[1].Start);
            Assert.Equal(baseDate.AddHours(13), merged[1].End);
        }

        [Fact]
        public void MergeIntervals_EmptyList_ShouldReturnEmpty()
        {
            // Arrange
            var intervals = new List<Interval>();

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Empty(merged);
        }

        [Fact]
        public void MergeIntervals_SingleInterval_ShouldReturnSame()
        {
            // Arrange
            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(11) }
            };

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Single(merged);
            Assert.Equal(baseDate.AddHours(10), merged[0].Start);
            Assert.Equal(baseDate.AddHours(11), merged[0].End);
        }

        [Fact]
        public void MergeIntervals_PartialOverlap_ShouldMergeCorrectly()
        {
            // Arrange
            // Desktop: 10:00 - 11:00 (60 min)
            // Android: 10:45 - 11:30 (45 min)
            // Raw: 60 + 45 = 105 min
            // Expected Merged: 10:00 - 11:30 = 90 min
            // Expected Overlap: 105 - 90 = 15 min

            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(11) },
                new Interval { Start = baseDate.AddHours(10).AddMinutes(45), End = baseDate.AddHours(11).AddMinutes(30) }
            };

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Single(merged);
            Assert.Equal(baseDate.AddHours(10), merged[0].Start);
            Assert.Equal(baseDate.AddHours(11).AddMinutes(30), merged[0].End);
            Assert.Equal(90 * 60, (int)(merged[0].End - merged[0].Start).TotalSeconds);
        }

        [Fact]
        public void MergeIntervals_MultipleOverlaps_ShouldMergeAll()
        {
            // Arrange
            // 10:00 - 10:30
            // 10:15 - 10:45
            // 10:30 - 11:00
            // Expected: 10:00 - 11:00

            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(10).AddMinutes(30) },
                new Interval { Start = baseDate.AddHours(10).AddMinutes(15), End = baseDate.AddHours(10).AddMinutes(45) },
                new Interval { Start = baseDate.AddHours(10).AddMinutes(30), End = baseDate.AddHours(11) }
            };

            // Act
            var merged = _service.MergeIntervals(intervals);

            // Assert
            Assert.Single(merged);
            Assert.Equal(baseDate.AddHours(10), merged[0].Start);
            Assert.Equal(baseDate.AddHours(11), merged[0].End);
            Assert.Equal(60 * 60, (int)(merged[0].End - merged[0].Start).TotalSeconds);
        }

        [Fact]
        public void CalculateAttentionTime_TripleOverlap_ShouldReturnCorrectDuration()
        {
            // Arrange
            var baseDate = DateTime.UtcNow.Date;
            var intervals = new List<Interval>
            {
                new Interval { Start = baseDate.AddHours(10), End = baseDate.AddHours(11) }, // 60 min
                new Interval { Start = baseDate.AddHours(10).AddMinutes(15), End = baseDate.AddHours(10).AddMinutes(45) }, // 30 min
                new Interval { Start = baseDate.AddHours(10).AddMinutes(20), End = baseDate.AddHours(10).AddMinutes(40) } // 20 min
            };

            // Act
            var attentionTime = _service.CalculateAttentionTime(intervals);

            // Assert
            Assert.Equal(60 * 60, attentionTime); // 60 minutes in seconds
        }
    }
}
