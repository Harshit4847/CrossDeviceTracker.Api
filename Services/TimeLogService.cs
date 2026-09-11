using System;
using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.EntityFrameworkCore;
using CrossDeviceTracker.Api.Exceptions;

namespace CrossDeviceTracker.Api.Services
{
    public class TimeLogService : ITimeLogService
    {
        private readonly AppDbContext _context;
        private readonly ICurrentDeviceService _currentDeviceService;
        private const int MaxLimit = 50;
        private const int DefaultLimit = 20;

        public TimeLogService(AppDbContext context, ICurrentDeviceService currentDeviceService)
        {
            _context = context;
            _currentDeviceService = currentDeviceService;
        }

        public async Task<PaginatedTimeLogsResponse> GetTimeLogsForUser(Guid userId, int? limit, DateTime? cursor)
        {
            int finalLimit = GetFinalLimit(limit);

            var timeLogs = await _context.TimeLogs.AsNoTracking()
                .Where(t => t.UserId == userId && (cursor == null || t.StartTime < cursor))
                .OrderByDescending(t => t.StartTime)
                .Take(finalLimit + 1)
                .ToListAsync();

            bool hasMore = timeLogs.Count > finalLimit;
            var items = timeLogs.Take(finalLimit).Select(MapToTimeLogResponse).ToList();
            DateTime? nextCursor = items.Any() ? items.Last().StartTime : null;

            return new PaginatedTimeLogsResponse
            {
                Items = items,
                NextCursor = nextCursor,
                HasMore = hasMore
            };
        }

        public async Task<TimeLogResponse> CreateTimeLog(Guid userid, CreateTimeLogRequest request)
        {
            if (request == null)
                throw new ArgumentNullException(nameof(request));

            if (request.DurationSeconds <= 0)
                throw new ArgumentException("DurationSeconds must be greater than 0", nameof(request.DurationSeconds));

            var deviceId = _currentDeviceService.DeviceId;
            var device = await _context.Devices.FirstOrDefaultAsync(d => d.Id == deviceId);

            if (device == null)
                throw new ForbiddenException("Device not found.");

            if (device.UserId != userid)
                throw new ForbiddenException("Device does not belong to the current user.");

            var timeLog = new TimeLog
            {
                Id = Guid.NewGuid(),
                UserId = userid,
                DeviceId = deviceId,
                ClientSessionId = request.ClientSessionId,
                AppName = string.IsNullOrWhiteSpace(request.AppName) ? request.PackageName ?? string.Empty : request.AppName,
                StartTime = request.StartTimeUtc,
                EndTime = request.EndTimeUtc,
                DurationSeconds = request.DurationSeconds,
                CreatedAt = request.CreatedAtUtc
            };

            device.LastDataSyncAt = DateTime.UtcNow;
            _context.TimeLogs.Add(timeLog);
            await _context.SaveChangesAsync();

            return MapToTimeLogResponse(timeLog);
        }

        public async Task<AcceptedTimeLogsResponse> CreateTimeLogsBatch(Guid userId, List<CreateTimeLogRequest> requests)
        {
            if (requests == null || requests.Count == 0)
                throw new ArgumentNullException(nameof(requests));

            var deviceId = _currentDeviceService.DeviceId;
            var device = await _context.Devices.FirstOrDefaultAsync(d => d.Id == deviceId);

            if (device == null)
                throw new ForbiddenException("Device not found.");

            if (device.UserId != userId)
                throw new ForbiddenException("Device does not belong to the current user.");

            foreach (var request in requests)
            {
                if (request == null)
                    throw new ArgumentNullException(nameof(request));

                if (string.IsNullOrWhiteSpace(request.ClientSessionId))
                    throw new ArgumentException("ClientSessionId is required for batch uploads.", nameof(requests));

                if (request.DurationSeconds <= 0)
                    throw new ArgumentException("DurationSeconds must be greater than 0", nameof(request.DurationSeconds));
            }

            // PostgreSQL enforces the unique (DeviceId, ClientSessionId) key.
            // Repeated uploads therefore become no-ops instead of duplicate rows.
            foreach (var request in requests)
            {
                var appName = string.IsNullOrWhiteSpace(request.AppName) ? request.PackageName ?? string.Empty : request.AppName;
                var id = Guid.NewGuid();

                await _context.Database.ExecuteSqlInterpolatedAsync($@"
                    INSERT INTO time_logs
                        (\"Id\", \"UserId\", \"DeviceId\", \"ClientSessionId\", \"AppName\", \"StartTime\", \"EndTime\", \"DurationSeconds\", \"CreatedAt\")
                    VALUES
                        ({id}, {userId}, {deviceId}, {request.ClientSessionId}, {appName}, {request.StartTimeUtc}, {request.EndTimeUtc}, {request.DurationSeconds}, {request.CreatedAtUtc})
                    ON CONFLICT (\"DeviceId\", \"ClientSessionId\") DO NOTHING");
            }

            device.LastDataSyncAt = DateTime.UtcNow;
            await _context.SaveChangesAsync();

            var acceptedIds = requests
                .Select(r => r.ClientSessionId!)
                .Distinct(StringComparer.Ordinal)
                .ToList();

            return new AcceptedTimeLogsResponse
            {
                AcceptedClientSessionIds = acceptedIds
            };
        }

        private int GetFinalLimit(int? limit)
        {
            if (!limit.HasValue)
                return DefaultLimit;

            return limit.Value > MaxLimit ? MaxLimit : limit.Value;
        }

        private TimeLogResponse MapToTimeLogResponse(TimeLog timeLog)
        {
            return new TimeLogResponse
            {
                Id = timeLog.Id,
                UserId = timeLog.UserId,
                CreatedAt = timeLog.CreatedAt,
                AppName = timeLog.AppName,
                DeviceId = timeLog.DeviceId,
                StartTime = timeLog.StartTime,
                EndTime = timeLog.EndTime,
                DurationSeconds = timeLog.DurationSeconds
            };
        }
    }
}

