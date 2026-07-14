using CrossDeviceTracker.Api.Models.DTOs.Dashboard;

namespace CrossDeviceTracker.Api.Services
{
    public interface IDashboardService
    {
        Task<DashboardSummaryResponse> GetSummaryAsync(Guid userId, DateTime? from = null, DateTime? to = null);
        Task<List<AppUsageResponse>> GetAppUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null, Guid? deviceId = null, string? platform = null);
        Task<List<DeviceUsageResponse>> GetDeviceUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null);
        Task<TimelineResponse> GetTimelineAsync(Guid userId, DateTime? from = null, DateTime? to = null);
        Task<DailyUsageResponse> GetDailyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null);
        Task<WeeklyUsageResponse> GetWeeklyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null);
        Task<MonthlyUsageResponse> GetMonthlyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null);
        Task<HourlyUsageResponse> GetHourlyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null);
    }
}
