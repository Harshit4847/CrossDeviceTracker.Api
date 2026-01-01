using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.EntityFrameworkCore;

namespace CrossDeviceTracker.Api.Services
{
    public class TimeLogService : ITimeLogService
    {
        private readonly AppDbContext _context;

        public TimeLogService(AppDbContext context) {
            
            _context = context;
        }

        public PaginatedTimeLogsResponse GetTimeLogsForUser(Guid userId, int? limit, string? cursor)
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


            //var timeLogs = _context.TimeLogs
            //           .Where(t => t.UserId == userId)
            //           .ToList();

            //List<TimeLogResponse> responses = new List<TimeLogResponse>();

            //foreach (var timeLog in timeLogs)
            //{
            //    responses.Add(new TimeLogResponse
            //    {
            //        Id = timeLog.Id,
            //        UserId = timeLog.UserId,
            //        CreatedAt = timeLog.CreatedAt,
            //        AppName = timeLog.AppName,
            //        DeviceId = timeLog.DeviceId,
            //        StartTime = timeLog.StartTime,
            //        EndTime = timeLog.EndTime,
            //        DurationSeconds = timeLog.DurationSeconds
            //    });
            //}

            return new PaginatedTimeLogsResponse();
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

