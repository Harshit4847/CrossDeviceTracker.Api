using System;

namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class CreateTimeLogRequest
    {
        public string AppName { get; set; } = string.Empty;

        public DateTime StartTime { get; set; }

        public int DurationSeconds { get; set; }
    }
}
