using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.EntityFrameworkCore;
using System.Linq;

namespace CrossDeviceTracker.Api.Services
{
    public class TimeLogService : ITimeLogService
    {
        private readonly AppDbContext _context;

        public TimeLogService(AppDbContext context) {
            
            _context = context;
        }

        public PaginatedTimeLogsResponse GetTimeLogsForUser(Guid userId, int? limit, DateTime? cursor)
        {
            //limit logic

            int maxLimit = 50;
            int defaultLimit = 20;

            int finalLimit;

            if (!limit.HasValue)
            {
                finalLimit = defaultLimit;
            }
            else if (limit.Value > maxLimit)
            {
                finalLimit = maxLimit;
            }
            else
            {
                finalLimit = limit.Value;
            }


            var timeLogs = _context.TimeLogs.AsNoTracking()
                       .Where(t => t.UserId == userId 
                            && (cursor == null || t.StartTime < cursor))
                       .OrderByDescending(t => t.StartTime)
                        .Take(finalLimit + 1)
                        .ToList();

            bool hasMore = timeLogs.Count > finalLimit;

            List<TimeLogResponse> items = new List<TimeLogResponse>();

            foreach (var timeLog in timeLogs.Take(finalLimit))
            {
                items.Add(new TimeLogResponse
                {
                    Id = timeLog.Id,
                    UserId = timeLog.UserId,
                    CreatedAt = timeLog.CreatedAt,
                    AppName = timeLog.AppName,
                    DeviceId = timeLog.DeviceId,
                    StartTime = timeLog.StartTime,
                    EndTime = timeLog.EndTime,
                    DurationSeconds = timeLog.DurationSeconds
                });
            }

            DateTime? nextCursor = items.Any() ? items.Last().StartTime : null;
           
            var response = new PaginatedTimeLogsResponse
            {
                Items = items,
                NextCursor = nextCursor,
                HasMore = hasMore
            };

            
            return response;
        }

        public TimeLogResponse CreateTimeLog(CreateTimeLogRequest request)
        {
            var timeLog = new TimeLog
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

            _context.TimeLogs.Add(timeLog);
            _context.SaveChanges();

            var response = new TimeLogResponse
            {
                Id = timeLog.Id,
                UserId = timeLog.UserId,
                DeviceId = timeLog.DeviceId,
                AppName = timeLog.AppName,
                StartTime = timeLog.StartTime,
                EndTime = timeLog.EndTime,
                DurationSeconds = timeLog.DurationSeconds,
                CreatedAt = timeLog.CreatedAt,
            };

            
            return response;
        }
    }
}

