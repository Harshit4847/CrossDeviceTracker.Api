using System;

namespace CrossDeviceTracker.Api.Models.Entities
{
    public class TimeLog
    {
        public Guid Id { get; set; }

        public Guid UserId { get; set; }

        public string AppName { get; set; } = string.Empty;

        public DateTime StartTime { get; set; }

        public DateTime EndTime { get; set; }

        public int DurationSeconds { get; set; }

        public DateTime CreatedAt { get; set; }
    }
}

