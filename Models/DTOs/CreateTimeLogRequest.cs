namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class CreateTimeLogRequest
    {
        public required string PackageName { get; set; }

        public string? AppName { get; set; }

        public DateTime StartTimeUtc { get; set; }

        public DateTime EndTimeUtc { get; set; }

        public int DurationSeconds { get; set; }

        public DateTime CreatedAtUtc { get; set; }
        
        public required string ClientSessionId { get; set; }
    }
}
