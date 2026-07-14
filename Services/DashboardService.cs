using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs.Dashboard;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;

namespace CrossDeviceTracker.Api.Services
{
    public class DashboardService : IDashboardService
    {
        private readonly AppDbContext _context;
        private readonly IMemoryCache _cache;
        private readonly ITimeAnalyticsService _timeAnalyticsService;

        public DashboardService(AppDbContext context, IMemoryCache cache, ITimeAnalyticsService timeAnalyticsService)
        {
            _context = context;
            _cache = cache;
            _timeAnalyticsService = timeAnalyticsService;
        }

        public async Task<DashboardSummaryResponse> GetSummaryAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var cacheKey = $"summary_{userId}_{from?.ToString("o")}_{to?.ToString("o")}";
            
            if (_cache.TryGetValue(cacheKey, out DashboardSummaryResponse? cached))
            {
                return cached!;
            }

            var now = DateTime.UtcNow;
            var today = now.Date;
            var yesterday = today.AddDays(-1);
            var weekStart = today.AddDays(-(int)now.DayOfWeek);
            var monthStart = new DateTime(now.Year, now.Month, 1);

            // Get all time logs for the user within date range if specified
            var query = _context.TimeLogs.Where(t => t.UserId == userId);
            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var userLogs = await query.ToListAsync();

            // Convert logs to intervals for merging
            var intervals = userLogs.Select(t => new Interval
            {
                Start = t.StartTime,
                End = t.EndTime
            }).ToList();

            // Calculate today's stats using interval merging
            var todayIntervals = intervals.Where(i => i.Start >= today).ToList();
            var todayRawDuration = userLogs.Where(t => t.StartTime >= today).Sum(t => t.DurationSeconds);
            var todayMergedDuration = _timeAnalyticsService.CalculateAttentionTime(todayIntervals);
            var todayStats = new TodayScreenTime
            {
                TotalScreenTimeSeconds = todayMergedDuration,
                TotalDeviceUsageSeconds = todayRawDuration,
                OverlapTimeSeconds = todayRawDuration - todayMergedDuration,
                SessionCount = todayIntervals.Count
            };

            // Calculate yesterday's stats using interval merging
            var yesterdayIntervals = intervals.Where(i => i.Start >= yesterday && i.Start < today).ToList();
            var yesterdayStats = new YesterdayScreenTime
            {
                TotalScreenTimeSeconds = _timeAnalyticsService.CalculateAttentionTime(yesterdayIntervals),
                SessionCount = yesterdayIntervals.Count
            };

            // Calculate this week's stats using interval merging
            var weekIntervals = intervals.Where(i => i.Start >= weekStart).ToList();
            var weekStats = new ThisWeekScreenTime
            {
                TotalScreenTimeSeconds = _timeAnalyticsService.CalculateAttentionTime(weekIntervals),
                SessionCount = weekIntervals.Count
            };

            // Calculate this month's stats using interval merging
            var monthIntervals = intervals.Where(i => i.Start >= monthStart).ToList();
            var monthStats = new ThisMonthScreenTime
            {
                TotalScreenTimeSeconds = _timeAnalyticsService.CalculateAttentionTime(monthIntervals),
                SessionCount = monthIntervals.Count
            };

            // Get device count
            var deviceCount = await _context.Devices.Where(d => d.UserId == userId).CountAsync();

            // Get app count
            var appCount = userLogs.Select(t => t.AppName).Distinct().Count();

            // Get most used app
            var mostUsedApp = userLogs
                .GroupBy(t => t.AppName)
                .Select(g => new { AppName = g.Key, Duration = g.Sum(t => t.DurationSeconds) })
                .OrderByDescending(g => g.Duration)
                .FirstOrDefault();

            var response = new DashboardSummaryResponse
            {
                Today = todayStats,
                Yesterday = yesterdayStats,
                ThisWeek = weekStats,
                ThisMonth = monthStats,
                DeviceCount = deviceCount,
                AppCount = appCount,
                MostUsedApp = mostUsedApp != null ? new MostUsedApp
                {
                    AppName = mostUsedApp.AppName,
                    DurationSeconds = mostUsedApp.Duration
                } : null
            };

            _cache.Set(cacheKey, response, TimeSpan.FromSeconds(10));
            return response;
        }

        public async Task<List<AppUsageResponse>> GetAppUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null, Guid? deviceId = null, string? platform = null)
        {
            var query = _context.TimeLogs.Where(t => t.UserId == userId);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);
            if (deviceId.HasValue) query = query.Where(t => t.DeviceId == deviceId.Value);

            var logs = await query.ToListAsync();

            if (!string.IsNullOrWhiteSpace(platform))
            {
                var deviceIds = await _context.Devices
                    .Where(d => d.UserId == userId && d.Platform == platform)
                    .Select(d => d.Id)
                    .ToListAsync();
                logs = logs.Where(t => deviceIds.Contains(t.DeviceId)).ToList();
            }

            // App usage uses raw duration (not merged) to show per-app time accurately
            var totalDuration = logs.Sum(t => t.DurationSeconds);

            var appUsage = logs
                .GroupBy(t => t.AppName)
                .Select(g => new AppUsageResponse
                {
                    AppName = g.Key,
                    DurationSeconds = g.Sum(t => t.DurationSeconds),
                    SessionCount = g.Count(),
                    Percentage = totalDuration > 0 ? (g.Sum(t => t.DurationSeconds) * 100.0) / totalDuration : 0
                })
                .OrderByDescending(a => a.DurationSeconds)
                .ToList();

            return appUsage;
        }

        public async Task<List<DeviceUsageResponse>> GetDeviceUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var query = _context.TimeLogs.Where(t => t.UserId == userId);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var logs = await query.ToListAsync();

            // Device usage uses raw duration (not merged) to show per-device time accurately
            var totalDuration = logs.Sum(t => t.DurationSeconds);

            var deviceIds = logs.Select(t => t.DeviceId).Distinct().ToList();
            var devices = await _context.Devices
                .Where(d => deviceIds.Contains(d.Id))
                .ToListAsync();

            var deviceUsage = logs
                .GroupBy(t => t.DeviceId)
                .Select(g => new
                {
                    DeviceId = g.Key,
                    DurationSeconds = g.Sum(t => t.DurationSeconds),
                    SessionCount = g.Count()
                })
                .Join(devices, g => g.DeviceId, d => d.Id, (g, d) => new DeviceUsageResponse
                {
                    DeviceName = d.DeviceName,
                    Platform = d.Platform,
                    DurationSeconds = g.DurationSeconds,
                    SessionCount = g.SessionCount,
                    Percentage = totalDuration > 0 ? (g.DurationSeconds * 100.0) / totalDuration : 0
                })
                .OrderByDescending(d => d.DurationSeconds)
                .ToList();

            return deviceUsage;
        }

        public async Task<TimelineResponse> GetTimelineAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var query = _context.TimeLogs
                .Where(t => t.UserId == userId)
                .Include(t => t.Device);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var logs = await query
                .OrderBy(t => t.StartTime)
                .ToListAsync();

            var entries = logs.Select(log => new TimelineEntry
            {
                Start = log.StartTime,
                End = log.EndTime,
                App = log.AppName,
                Device = log.Device?.DeviceName ?? "Unknown",
                Platform = log.Device?.Platform ?? "Unknown",
                DurationSeconds = log.DurationSeconds
            }).ToList();

            return new TimelineResponse { Entries = entries };
        }

        public async Task<DailyUsageResponse> GetDailyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var query = _context.TimeLogs.Where(t => t.UserId == userId);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var logs = await query.ToListAsync();

            var dailyEntries = logs
                .GroupBy(t => t.StartTime.Date)
                .Select(g =>
                {
                    var dayIntervals = g.Select(t => new Interval
                    {
                        Start = t.StartTime,
                        End = t.EndTime
                    }).ToList();
                    return new DailyEntry
                    {
                        Date = g.Key,
                        DurationSeconds = _timeAnalyticsService.CalculateAttentionTime(dayIntervals),
                        SessionCount = g.Count()
                    };
                })
                .OrderBy(d => d.Date)
                .ToList();

            return new DailyUsageResponse { Days = dailyEntries };
        }

        public async Task<WeeklyUsageResponse> GetWeeklyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var query = _context.TimeLogs.Where(t => t.UserId == userId);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var logs = await query.ToListAsync();

            var weeklyEntries = logs
                .GroupBy(t => System.Globalization.CultureInfo.InvariantCulture.Calendar.GetWeekOfYear(
                    t.StartTime, System.Globalization.CalendarWeekRule.FirstFourDayWeek, DayOfWeek.Sunday))
                .Select(g =>
                {
                    var weekIntervals = g.Select(t => new Interval
                    {
                        Start = t.StartTime,
                        End = t.EndTime
                    }).ToList();
                    return new WeeklyEntry
                    {
                        WeekStart = g.Min(t => t.StartTime.Date.AddDays(-(int)t.StartTime.DayOfWeek)),
                        WeekEnd = g.Max(t => t.StartTime.Date.AddDays(6 - (int)t.StartTime.DayOfWeek)),
                        DurationSeconds = _timeAnalyticsService.CalculateAttentionTime(weekIntervals),
                        SessionCount = g.Count()
                    };
                })
                .OrderBy(w => w.WeekStart)
                .ToList();

            return new WeeklyUsageResponse { Weeks = weeklyEntries };
        }

        public async Task<MonthlyUsageResponse> GetMonthlyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var query = _context.TimeLogs.Where(t => t.UserId == userId);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var logs = await query.ToListAsync();

            var monthlyEntries = logs
                .GroupBy(t => new { t.StartTime.Year, t.StartTime.Month })
                .Select(g =>
                {
                    var monthIntervals = g.Select(t => new Interval
                    {
                        Start = t.StartTime,
                        End = t.EndTime
                    }).ToList();
                    return new MonthlyEntry
                    {
                        Year = g.Key.Year,
                        Month = g.Key.Month,
                        DurationSeconds = _timeAnalyticsService.CalculateAttentionTime(monthIntervals),
                        SessionCount = g.Count()
                    };
                })
                .OrderBy(m => m.Year)
                .ThenBy(m => m.Month)
                .ToList();

            return new MonthlyUsageResponse { Months = monthlyEntries };
        }

        public async Task<HourlyUsageResponse> GetHourlyUsageAsync(Guid userId, DateTime? from = null, DateTime? to = null)
        {
            var query = _context.TimeLogs.Where(t => t.UserId == userId);

            if (from.HasValue) query = query.Where(t => t.StartTime >= from.Value);
            if (to.HasValue) query = query.Where(t => t.StartTime <= to.Value);

            var logs = await query.ToListAsync();

            var hourlyEntries = Enumerable.Range(0, 24)
                .Select(hour =>
                {
                    var hourLogs = logs.Where(t => t.StartTime.Hour == hour).ToList();
                    var hourIntervals = hourLogs.Select(t => new Interval
                    {
                        Start = t.StartTime,
                        End = t.EndTime
                    }).ToList();
                    return new HourlyEntry
                    {
                        Hour = hour,
                        DurationSeconds = _timeAnalyticsService.CalculateAttentionTime(hourIntervals),
                        SessionCount = hourLogs.Count
                    };
                })
                .OrderBy(h => h.Hour)
                .ToList();

            return new HourlyUsageResponse { Hours = hourlyEntries };
        }
    }
}
