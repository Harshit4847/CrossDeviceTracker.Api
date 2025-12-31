using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrossDeviceTracker.Api.Controllers
{
    [ApiController]
    [Route("api/timelogs")]
    public class TimeLogsController : ControllerBase
    {
        private readonly ITimeLogService _timeLogService;
        public TimeLogsController(ITimeLogService timeLogService)
        {
            _timeLogService = timeLogService;
        }

        [HttpPost]
        public IActionResult CreateTimeLog([FromBody] CreateTimeLogRequest request)
        {
            if(request.StartTime > DateTime.UtcNow)
            {
                return BadRequest("StartTime cannot be in the future");
            }
            var response = _timeLogService.CreateTimeLog(request);


            return Ok(response);
        }

        [HttpGet("user/{userId}")]
        public IActionResult GetTimeLogsForUser(Guid userId)
        {

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }
            var response = _timeLogService.GetTimeLogsForUser(userId);

            return Ok(response);
        }
    }
}