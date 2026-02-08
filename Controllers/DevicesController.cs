    using Microsoft.AspNetCore.Mvc;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Models.DTOs;
using Microsoft.AspNetCore.Authorization;

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
            if (userId == null || userId == Guid.Empty)
            {
                return Unauthorized("UserId is invalid");
            }

            var responses = _deviceService.GetDevicesForUser(userId.Value);
            return Ok(responses);
        }

        [Authorize]
        [HttpPost]
        public IActionResult CreateDevice([FromBody] CreateDeviceRequest request)
        {
            var userId = _currentUserService.UserId;
            if (userId == null || userId == Guid.Empty)
            {
                return Unauthorized("UserId is invalid");
            }

            if (request == null)
            {
                return BadRequest("Request body is null");
            }

            if (string.IsNullOrWhiteSpace(request.DeviceName))
            {
                return BadRequest("DeviceName is required");
            }

            if (string.IsNullOrWhiteSpace(request.Platform))
            {
                return BadRequest("Platform is required");
            }

            var response = _deviceService.CreateDevice(userId.Value, request);

            
            return CreatedAtAction(nameof(GetDevicesForUser), new { userId }, response.Device);
            

            
        }
    }
}
