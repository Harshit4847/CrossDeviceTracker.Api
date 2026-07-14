using CrossDeviceTracker.Api.Models.DTOs.Dashboard;
using CrossDeviceTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace CrossDeviceTracker.Api.Controllers
{
    [Authorize]
    [ApiController]
    [Route("api/dashboard")]
    public class DashboardController : ControllerBase
    {
        private readonly IDashboardService _dashboardService;
        private readonly ICurrentUserService _currentUserService;

        public DashboardController(IDashboardService dashboardService, ICurrentUserService currentUserService)
        {
            _dashboardService = dashboardService;
            _currentUserService = currentUserService;
        }

        [HttpGet("summary")]
        public async Task<IActionResult> GetSummary([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetSummaryAsync(userId, from, to);

            return Ok(response);
        }

        [HttpGet("apps")]
        public async Task<IActionResult> GetAppUsage([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null, [FromQuery] Guid? deviceId = null, [FromQuery] string? platform = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetAppUsageAsync(userId, from, to, deviceId, platform);

            return Ok(response);
        }

        [HttpGet("devices")]
        public async Task<IActionResult> GetDeviceUsage([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetDeviceUsageAsync(userId, from, to);

            return Ok(response);
        }

        [HttpGet("timeline")]
        public async Task<IActionResult> GetTimeline([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetTimelineAsync(userId, from, to);

            return Ok(response);
        }
    }

    [Authorize]
    [ApiController]
    [Route("api/analytics")]
    public class AnalyticsController : ControllerBase
    {
        private readonly IDashboardService _dashboardService;
        private readonly ICurrentUserService _currentUserService;

        public AnalyticsController(IDashboardService dashboardService, ICurrentUserService currentUserService)
        {
            _dashboardService = dashboardService;
            _currentUserService = currentUserService;
        }

        [HttpGet("daily")]
        public async Task<IActionResult> GetDailyUsage([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetDailyUsageAsync(userId, from, to);

            return Ok(response);
        }

        [HttpGet("weekly")]
        public async Task<IActionResult> GetWeeklyUsage([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetWeeklyUsageAsync(userId, from, to);

            return Ok(response);
        }

        [HttpGet("monthly")]
        public async Task<IActionResult> GetMonthlyUsage([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetMonthlyUsageAsync(userId, from, to);

            return Ok(response);
        }

        [HttpGet("hourly")]
        public async Task<IActionResult> GetHourlyUsage([FromQuery] DateTime? from = null, [FromQuery] DateTime? to = null)
        {
            var userId = _currentUserService.UserId;

            if (userId == Guid.Empty)
            {
                return BadRequest("UserId is empty / invalid");
            }

            var response = await _dashboardService.GetHourlyUsageAsync(userId, from, to);

            return Ok(response);
        }
    }
}
