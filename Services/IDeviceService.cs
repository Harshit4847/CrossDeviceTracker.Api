using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Commands;

namespace CrossDeviceTracker.Api.Services
{
    public interface IDeviceService
    {
        //for android and mac
        RegisterDeviceResponse CreateDevice(Guid UserId, CreateDeviceRequest request);
        List<DeviceResponse> GetDevicesForUser(Guid userId);

        //for desktop
        Task<GenerateDesktopLinkTokenResponse> GenerateDesktopLinkTokenAsync(Guid userId);
        Task<LinkDesktopResponse> LinkDesktopAsync(Guid authenticatedUserId, LinkDesktopCommand command);
    }
}
