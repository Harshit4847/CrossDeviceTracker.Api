using CrossDeviceTracker.Api.Models.DTOs;
using System.Collections.Generic;

namespace CrossDeviceTracker.Api.Services
{
    public interface ITimeLogService
    {
        PaginatedTimeLogsResponse GetTimeLogsForUser(Guid userId, int? limit, DateTime? cursor);
        TimeLogResponse CreateTimeLog(CreateTimeLogRequest request);
    }
}

