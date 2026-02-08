namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class CreateDeviceRequest
    {
        public string DeviceName { get; set; } = string.Empty;

        public string Platform {  get; set; } = string.Empty;

    }
}
