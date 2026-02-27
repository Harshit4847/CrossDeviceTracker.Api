using CrossDeviceTracker.Api.Models.DTOs;

namespace CrossDeviceTracker.Api.Services
{
    public interface IDeviceService
    {
        DeviceResult CreateDevice(Guid UserId, CreateDeviceRequest request);
        List<DeviceResponse> GetDevicesForUser(Guid userId);

        Task<GenerateDesktopLinkTokenResponse> GenerateDesktopLinkTokenAsync(Guid userId);
    }
}
