using CrossDeviceTracker.Api.Models.DTOs;

namespace CrossDeviceTracker.Api.Services
{
    public interface IDeviceService
    {
        public DeviceResult CreateDevice(CreateDeviceRequest request);
        public List<DeviceResponse> GetDevicesForUser( Guid userId );

    }
}
