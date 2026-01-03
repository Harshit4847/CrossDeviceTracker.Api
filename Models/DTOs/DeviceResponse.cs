namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class DeviceResponse
    {
        public Guid Id { get; set; }

        public Guid UserId { get; set; }

        public string DeviceName { get; set; } = string.Empty;

        public string Platform { get; set; } = string.Empty;

        public DateTime CreatedAt { get; set; }
    }
}
