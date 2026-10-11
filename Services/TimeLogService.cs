using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.EntityFrameworkCore;
using CrossDeviceTracker.Api.Exceptions;
using Npgsql;
using System.Text;

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
            {
                throw new ArgumentNullException(nameof(request));
            }

            if (request.DurationSeconds <= 0)
            {
                throw new ArgumentException("DurationSeconds must be greater than 0", nameof(request.DurationSeconds));
            }

            var deviceId = _currentDeviceService.DeviceId;

            var device = await _context.Devices.FirstOrDefaultAsync(d => d.Id == deviceId);

            if (device == null)
            {
                throw new ForbiddenException("Device not found.");
            }

            if (device.UserId != userid)
            {
                throw new ForbiddenException("Device does not belong to the current user.");
            }

            var timeLog = new TimeLog
            {
                Id = Guid.NewGuid(),
                UserId = userid,
                DeviceId = deviceId,
                AppName = string.IsNullOrWhiteSpace(request.AppName) ? request.PackageName : request.AppName,
                StartTime = request.StartTimeUtc,
                EndTime = request.EndTimeUtc,
                DurationSeconds = request.DurationSeconds,
                CreatedAt = request.CreatedAtUtc,
                ClientSessionId = request.ClientSessionId
            };

            device.LastDataSyncAt = DateTime.UtcNow;
            _context.TimeLogs.Add(timeLog);
            await _context.SaveChangesAsync();

            return MapToTimeLogResponse(timeLog);
        }

        public async Task<CreateTimeLogsBatchResponse> CreateTimeLogsBatch(Guid userId,
            List<CreateTimeLogRequest> requests)
        {
            if (requests == null || requests.Count == 0)
            {
                throw new ArgumentNullException(nameof(requests));
            }

            var deviceId = _currentDeviceService.DeviceId;

            var device = await _context.Devices.FirstOrDefaultAsync(d => d.Id == deviceId);
            
            Console.WriteLine($"Service DeviceId: {deviceId}");
            Console.WriteLine($"Found Device: {device != null}");

            if (device == null)
            {
                throw new ForbiddenException("Device not found.");
            }

            if (device.UserId != userId)
            {
                throw new ForbiddenException("Device does not belong to the current user.");
            }

            foreach (var request in requests)
            {
                if (request == null)
                {
                    throw new ArgumentNullException(nameof(request));
                }
            }

            var distinct = requests.DistinctBy(request => request.ClientSessionId).ToList();
            var response = new CreateTimeLogsBatchResponse { AcceptedClientSessionIds = new List<string>() };

            foreach (var request in distinct)
            {
                if (request.DurationSeconds <= 0)
                {
                    throw new ArgumentException("DurationSeconds must be greater than 0",
                        nameof(request.DurationSeconds));
                }

                response.AcceptedClientSessionIds.Add(request.ClientSessionId);
            }

            await using var transaction = await _context.Database.BeginTransactionAsync();
            var sql = new StringBuilder();
            var parameters = new List<NpgsqlParameter>();

            sql.Append(
                "INSERT INTO time_logs (\"Id\", \"UserId\", \"DeviceId\", \"AppName\", \"StartTime\", \"EndTime\", \"DurationSeconds\", \"CreatedAt\", \"ClientSessionId\") VALUES ");
            foreach (var request in distinct)
            {
                var index = distinct.IndexOf(request);
                sql.Append("(");
                sql.Append(
                    $"@id{index}, @userId{index}, @deviceId{index}, @appName{index}, @startTime{index}, @endTime{index}, @durationSeconds{index}, @createdAt{index}, @clientSessionId{index}");
                sql.Append(")");
                parameters.Add(new NpgsqlParameter($"@id{index}", Guid.NewGuid()));
                parameters.Add(new NpgsqlParameter($"@userId{index}", userId));
                parameters.Add(new NpgsqlParameter($"@deviceId{index}", deviceId));
                parameters.Add(new NpgsqlParameter($"@appName{index}",
                    string.IsNullOrWhiteSpace(request.AppName) ? request.PackageName : request.AppName));
                parameters.Add(new NpgsqlParameter($"@startTime{index}", request.StartTimeUtc));
                parameters.Add(new NpgsqlParameter($"@endTime{index}", request.EndTimeUtc));
                parameters.Add(new NpgsqlParameter($"@durationSeconds{index}", request.DurationSeconds));
                parameters.Add(new NpgsqlParameter($"@createdAt{index}", request.CreatedAtUtc));
                parameters.Add(new NpgsqlParameter($"@clientSessionId{index}", request.ClientSessionId));
                sql.Append(",");
            }

            sql.Length--;
            sql.Append(" ON CONFLICT (\"ClientSessionId\", \"DeviceId\") DO NOTHING");


            device.LastDataSyncAt = DateTime.UtcNow;
            try
            {
                await _context.SaveChangesAsync();
                await _context.Database.ExecuteSqlRawAsync(sql.ToString(), parameters);
                await transaction.CommitAsync();
            }
            catch (Exception e)
            {
                await transaction.RollbackAsync();
                throw;
            }

            return response;
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