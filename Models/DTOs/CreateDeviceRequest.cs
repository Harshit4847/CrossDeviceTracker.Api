namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class CreateDeviceRequest
    {
        public Guid UserId { get; set; }

        public string DeviceName { get; set; } = string.Empty;

        public string Platform {  get; set; } = string.Empty;

        public Guid DeviceId { get; set; }
    }
}
