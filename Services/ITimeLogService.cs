using CrossDeviceTracker.Api.Models.DTOs;
using System.Collections.Generic;

namespace CrossDeviceTracker.Api.Services
{
    public interface ITimeLogService
    {
        Task<PaginatedTimeLogsResponse> GetTimeLogsForUser(Guid userId, int? limit, DateTime? cursor);
        Task<TimeLogResponse> CreateTimeLog(Guid userid, CreateTimeLogRequest request);
        Task<AcceptedTimeLogsResponse> CreateTimeLogsBatch(Guid userId, List<CreateTimeLogRequest> requests);
    }
}

