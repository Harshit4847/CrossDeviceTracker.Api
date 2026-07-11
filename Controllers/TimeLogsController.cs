using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System;
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
            if(userId== Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            if (string.IsNullOrWhiteSpace(request.AppName) && string.IsNullOrWhiteSpace(request.PackageName))
            {
                return BadRequest("AppName or PackageName is required");
            }
            if (request.StartTimeUtc > DateTime.UtcNow)
            {
                return BadRequest("StartTimeUtc cannot be in the future");
            }

            if (request.EndTimeUtc <= request.StartTimeUtc)
            {
                return BadRequest("EndTimeUtc must be after StartTimeUtc");
            }

            var computedDuration = (request.EndTimeUtc - request.StartTimeUtc).TotalSeconds;
            if (Math.Abs(computedDuration - request.DurationSeconds) > 1.0)
            {
                return BadRequest("DurationSeconds must match (EndTimeUtc - StartTimeUtc)");
            }

            if(request.DurationSeconds <= 0)
            {
                return BadRequest("DurationSeconds must be greater than zero");
            }
            var response = await _timeLogService.CreateTimeLog(userId, request);


            return Ok(response);
        }

        [HttpPost("batch")]
        public async Task<IActionResult> CreateTimeLogsBatch([FromBody] List<CreateTimeLogRequest> requests)
        {
            var userId = _currentUserService.UserId;
            if (requests == null || requests.Count == 0)
            {
                return BadRequest("Request body is null or empty");
            }
            if(userId== Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            foreach (var request in requests)
            {
                if (request == null)
                {
                    return BadRequest("Request contains null item");
                }

                if (string.IsNullOrWhiteSpace(request.AppName) && string.IsNullOrWhiteSpace(request.PackageName))
                {
                    return BadRequest("AppName or PackageName is required for all items");
                }

                if (request.StartTimeUtc > DateTime.UtcNow)
                {
                    return BadRequest("StartTimeUtc cannot be in the future");
                }

                if (request.EndTimeUtc <= request.StartTimeUtc)
                {
                    return BadRequest("EndTimeUtc must be after StartTimeUtc");
                }

                var computedDuration = (request.EndTimeUtc - request.StartTimeUtc).TotalSeconds;
                if (Math.Abs(computedDuration - request.DurationSeconds) > 1.0)
                {
                    return BadRequest("DurationSeconds must match (EndTimeUtc - StartTimeUtc)");
                }

                if (request.DurationSeconds <= 0)
                {
                    return BadRequest("DurationSeconds must be greater than zero");
                }
            }

            var response = await _timeLogService.CreateTimeLogsBatch(userId, requests);

            return Ok(response);
        }

        [Authorize]
        [HttpGet]
        public async Task<IActionResult> GetTimeLogsForUser([FromQuery] int? limit, [FromQuery] DateTime? cursor)
        {
            var userId = _currentUserService.UserId;
            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            

            var response = await _timeLogService.GetTimeLogsForUser(userId, limit, cursor);

            return Ok(response);
        }
    }
}