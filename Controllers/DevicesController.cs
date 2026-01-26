using Microsoft.AspNetCore.Mvc;
using CrossDeviceTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;


namespace CrossDeviceTracker.Api.Controllers
{
    [ApiController]
    [Route("api/devices")]

    public class DevicesController : ControllerBase
    {
        public readonly IDeviceService _deviceService;

        public DevicesController(IDeviceService deviceService)
        {
            _deviceService = deviceService;
        }

        [Authorize]
        [HttpGet("user/{userId}")]
        public IActionResult GetDevicesForUser(Guid userId)
        {
            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            var responses = _deviceService.GetDevicesForUser(userId);
            return Ok(responses);
        }

        [HttpPost]
        public IActionResult CreateDevice([FromBody] Models.DTOs.CreateDeviceRequest request)
        {
            if (request == null)
            {
                return BadRequest("Request body is null");
            }
            if (request.UserId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            if (string.IsNullOrWhiteSpace(request.DeviceName))
            {
                return BadRequest("DeviceName is required");
            }
            if (string.IsNullOrWhiteSpace(request.Platform))
            {
                return BadRequest("Platform is required");
            }
            if( request.DeviceId == Guid.Empty)
            {
                return BadRequest("DeviceId is required");
            }


            var response = _deviceService.CreateDevice(request);

            if (response.WasCreated == true)
            {
                return CreatedAtAction(nameof(GetDevicesForUser), new { userId = request.UserId }, response.Device);
            }
            else
            {
                return Ok(response.Device);
            }
        }

    }
}
