using CrossDeviceTracker.Api.Models.DTOs;

namespace CrossDeviceTracker.Api.Services
{
    public interface ITimeLogService
    {
        List<TimeLogResponse> GetTimeLogsForUser(Guid userId);
        TimeLogResponse CreateTimeLog(CreateTimeLogRequest request);
    }
}

