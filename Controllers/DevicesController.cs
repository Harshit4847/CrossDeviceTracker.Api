using Microsoft.AspNetCore.Mvc;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Models.DTOs;
using Microsoft.AspNetCore.Authorization;
using CrossDeviceTracker.Api.Models.Commands;

namespace CrossDeviceTracker.Api.Controllers
{
    [ApiController]
    [Route("api/devices")]
    public class DevicesController : ControllerBase
    {
        private readonly IDeviceService _deviceService;
        private readonly ICurrentUserService _currentUserService;

        public DevicesController(IDeviceService deviceService, ICurrentUserService currentUserService)
        {
            _deviceService = deviceService;
            _currentUserService = currentUserService;
        }

        [Authorize]
        [HttpGet]
        public IActionResult GetDevicesForUser()
        {
            var userId = _currentUserService.UserId;

            var responses = _deviceService.GetDevicesForUser(userId);
            return Ok(responses);
        }

        [Authorize]
        [HttpPost]
        public IActionResult CreateDevice([FromBody] CreateDeviceRequest request)
        {
            var userId = _currentUserService.UserId;

            var response = _deviceService.CreateDevice(userId, request);

            if (!response.WasCreated)
            {
                return Ok(response);
            }

            return CreatedAtAction(nameof(GetDevicesForUser), new { userId }, response);
            
        }

        [Authorize]
        [HttpPost("link-token")]
        public async Task<IActionResult> GenerateDesktopLinkToken()
        {
            var userId = _currentUserService.UserId;

            var response = await _deviceService.GenerateDesktopLinkTokenAsync(userId);
            return Ok(response);
        }

        [Authorize]
        [HttpPost("link")]
        public async Task<IActionResult> LinkDesktopAsync([FromBody] LinkDesktopRequest request)
        {
            var userId = _currentUserService.UserId;

            var command = new LinkDesktopCommand(request.LinkToken,request.DeviceName,request.Platform);

            var response = await _deviceService.LinkDesktopAsync(userId, command);
            return Ok(response);
        }
    }
}
