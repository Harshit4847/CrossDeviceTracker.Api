using CrossDeviceTracker.Api.Models.DTOs;

namespace CrossDeviceTracker.Api.Services
{
    public interface ITimeLogService
    {
        List<TimeLogResponse> GetTimeLogsForUser(int userId);
    }
}

