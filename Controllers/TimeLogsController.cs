using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Collections.Generic;

namespace CrossDeviceTracker.Api.Controllers
{
    [Authorize]
    [ApiController]
    [Route("api/timelogs")]

    public class TimeLogsController : ControllerBase
    {
        private readonly ITimeLogService _timeLogService;
        private readonly ICurrentUserService _currentUserService;

        public TimeLogsController(ITimeLogService timeLogService, ICurrentUserService currentUserService)
        {
            _timeLogService = timeLogService;
            _currentUserService = currentUserService;
        }

        [HttpPost]
        public async Task<IActionResult> CreateTimeLog([FromBody] CreateTimeLogRequest request)
        {
            var userId = _currentUserService.UserId;
            if (request == null)
            {
                return BadRequest("Request body is null");
            }
            if (!userId.HasValue || userId.Value == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            if(request.DeviceId == Guid.Empty)
            {
                return BadRequest("DeviceId is empty / invalid");
            }
            if(string.IsNullOrWhiteSpace(request.AppName))
            {
                return BadRequest("AppName is required");
            }
            if (request.StartTime > DateTime.UtcNow)
            {
                return BadRequest("StartTime cannot be in the future");
            }

            if(request.DurationSeconds <= 0)
            {
                return BadRequest("DurationSeconds must be greater than zero");
            }
            var response = await _timeLogService.CreateTimeLog(userId.Value, request);


            return Ok(response);
        }

        [Authorize]
        [HttpGet]
        public async Task<IActionResult> GetTimeLogsForUser([FromQuery] int? limit, [FromQuery] DateTime? cursor)
        {
            var userId = _currentUserService.UserId;
            if (!userId.HasValue || userId.Value == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            

            var response = await _timeLogService.GetTimeLogsForUser(userId.Value, limit, cursor);

            return Ok(response);
        }
    }
}