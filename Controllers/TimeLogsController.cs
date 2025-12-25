using Microsoft.AspNetCore.Mvc;
using CrossDeviceTracker.Api.Models.DTOs;

namespace CrossDeviceTracker.Api.Controllers
{
    [ApiController]
    [Route("api/timelogs")]
    public class TimeLogsController : ControllerBase
    {
        // For now, no service yet – we’ll add it next
        public TimeLogsController()
        {
        }

        [HttpPost]
        public IActionResult CreateTimeLog([FromBody] CreateTimeLogRequest request)
        {
            // TEMP response (until service is added)
            var response = new TimeLogResponse
            {
                Id = Guid.NewGuid(),
                UserId = request.UserId,
                DeviceId = request.DeviceId,
                AppName = request.AppName,
                StartTime = request.StartTime,
                EndTime = request.StartTime.AddSeconds(request.DurationSeconds),
                DurationSeconds = request.DurationSeconds,
                CreatedAt = DateTime.UtcNow
            };

            return Ok(new
            {
                success = true,
                message = "Time log created successfully",
                data = response
            });
        }
    }
}
