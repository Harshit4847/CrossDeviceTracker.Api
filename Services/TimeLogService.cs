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
        private const int MaxLimit = 50;
        private const int DefaultLimit = 20;
        

        public TimeLogService(AppDbContext context)
        {
            _context = context;
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
            {
                throw new ArgumentNullException(nameof(request));
            }

            if (request.DurationSeconds <= 0)
            {
                throw new ArgumentException("DurationSeconds must be greater than 0", nameof(request.DurationSeconds));
            }

            var deviceExists = await _context.Devices.AnyAsync(d => d.Id == request.DeviceId && d.UserId == userid);

            if (!deviceExists)
            {
                throw new ForbiddenException("Device not found for the user", nameof(request.DeviceId));
            }

            var timeLog = new TimeLog
            {
                Id = Guid.NewGuid(),
                UserId = userid,
                DeviceId = request.DeviceId,
                AppName = request.AppName,
                StartTime = request.StartTime,
                EndTime = request.StartTime.AddSeconds(request.DurationSeconds),
                DurationSeconds = request.DurationSeconds,
                CreatedAt = DateTime.UtcNow
            };

            _context.TimeLogs.Add(timeLog);
            await _context.SaveChangesAsync();

            return MapToTimeLogResponse(timeLog);
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

