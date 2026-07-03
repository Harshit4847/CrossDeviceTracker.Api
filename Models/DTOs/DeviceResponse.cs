namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class DeviceResponse
    {
        public Guid Id { get; set; }

        public Guid UserId { get; set; }

        public string DeviceName { get; set; } = string.Empty;

        public string Platform { get; set; } = string.Empty;

        public string? InstallationId { get; set; }

        public int TokenVersion { get; set; }

        public bool IsRevoked { get; set; }

        public DateTime? LastDataSyncAt { get; set; }

        public DateTime CreatedAt { get; set; }
    }
}
