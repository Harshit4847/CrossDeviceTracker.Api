namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class RegisterDeviceResponse
    {
        public Guid DeviceId { get; set; }
        public string DeviceJwt { get; set; } = string.Empty;
        public bool WasCreated { get; set; }
        public string DeviceName { get; set; } = string.Empty;
        public string Platform { get; set; } = string.Empty;
    }
}
