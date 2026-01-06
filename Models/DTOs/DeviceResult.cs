using CrossDeviceTracker.Api.Models.Entities;

namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class DeviceResult
    {
        public DeviceResponse Device { get; set; } = new DeviceResponse();
        public bool WasCreated { get; set; }
    }
}
