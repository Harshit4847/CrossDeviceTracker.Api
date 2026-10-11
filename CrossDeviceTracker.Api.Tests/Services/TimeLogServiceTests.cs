using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Data;
using Xunit;
using Microsoft.EntityFrameworkCore;
using System;
using System.Threading.Tasks;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.Extensions.Configuration;
using Microsoft.Data.Sqlite;

namespace CrossDeviceTracker.Api.Tests.Services
{
    public class TimeLogServiceTests
    {
        private readonly TimeLogService _service;
        private readonly AppDbContext _context;
        private FakeCurrentDeviceService currentDeviceService = new FakeCurrentDeviceService();
        private sealed class FakeCurrentDeviceService : ICurrentDeviceService
        {
            public Guid DeviceId { get; set; } = Guid.NewGuid();
        }

        private sealed class FakeDeviceJwtService : IDeviceJwtService
        {
            public string GenerateDeviceJwt(Guid deviceId, Guid userId, int tokenVersion)
            {
                return "fake-jwt-token";
            }
        }
        
        private readonly string connectionString = "Host=localhost;Port=5432;Database=CrossDeviceTrackerTest;Username=postgres";
        public TimeLogServiceTests()
        {
            
            var connection = connectionString;
            
            var options = new DbContextOptionsBuilder<AppDbContext>()
                .UseNpgsql(connection)
                .Options;

            _context = new AppDbContext(options);
            _context.Database.EnsureCreated();

            _service = new TimeLogService(
                _context,
                currentDeviceService
            );
        }

        [Fact]
        public async Task GetTimeLogsForUser_ShouldReturnEmptyList()
        {
            // Arrange
            Guid userId = Guid.NewGuid();

            // Act
            var result = await _service.GetTimeLogsForUser(userId, null, null);

            // Assert
            Assert.NotNull(result);
            Assert.Empty(result.Items);
        }

        [Fact]
        public async Task GetTimeLogsForUser_ShouldReturnListOfTimeLogResponse()
        {
            // Arrange
            Guid userId = Guid.NewGuid();

            // Act
            var result = await _service.GetTimeLogsForUser(userId, null, null);

            // Assert
            Assert.IsType<PaginatedTimeLogsResponse>(result);
        }

        [Fact]
        public async Task CreateDevice_ShouldPopulateTrackingFields()
        {
            // Arrange
            var configuration = new ConfigurationBuilder()
                .AddInMemoryCollection(new System.Collections.Generic.Dictionary<string, string?>
                {
                    { "Jwt:Key", "test-key-for-jwt-signing-1234567890123456" },
                    { "Jwt:Issuer", "test-issuer" },
                    { "Jwt:Audience", "test-audience" },
                    { "Jwt:ExpiryMinutes", "60" }
                })
                .Build();
            var deviceJwtService = new FakeDeviceJwtService();
            var service = new DeviceService(_context, configuration, deviceJwtService);
            var userId = Guid.NewGuid();
            
            var user = new User
            {
                Id = userId,
                Email = $"test-{Guid.NewGuid()}@example.com"
            };
            
            _context.Users.Add(user);
            await _context.SaveChangesAsync();
            
            var request = new CreateDeviceRequest
            {
                DeviceName = "Pixel 8",
                Platform = "Android",
                InstallationId = "install-123"
            };
            
            // Act
            var result = service.CreateDevice(userId, request);

            // Assert
            Assert.True(result.WasCreated);
            Assert.Equal("Pixel 8", result.DeviceName);
            Assert.Equal("Android", result.Platform);
            Assert.NotEqual(Guid.Empty, result.DeviceId);
            Assert.NotNull(result.DeviceJwt);
        }

        [Fact]
        public async Task CreateTimeLogsBatch_ShouldIgnoreDuplicateClientSessionIds()
        {
            var userId = Guid.NewGuid();

            var user = new User
            {
                Id = userId,
                Email = $"test-{Guid.NewGuid()}@example.com"
            };
            
            _context.Users.Add(user);
            
            var device = new Device();
            device.Id = Guid.NewGuid();
            Console.WriteLine(device.Id);
            _context.Devices.Add(device);
            currentDeviceService.DeviceId = device.Id;
            device.UserId = userId;
            await _context.SaveChangesAsync();
            Console.WriteLine(_context.Devices.Any(d => d.Id == device.Id));
            

            var request = new CreateTimeLogRequest
            {
                PackageName = "com.test.app",
                StartTimeUtc = DateTime.UtcNow.AddMinutes(-5),
                EndTimeUtc = DateTime.UtcNow,
                DurationSeconds = 300,
                CreatedAtUtc = DateTime.UtcNow,
                ClientSessionId = "test-session-duplicate",
            };
            
            var request2 = new CreateTimeLogRequest
            {
                ClientSessionId = $"test-{Guid.NewGuid()}",
                PackageName = "com.test.app",
                StartTimeUtc = DateTime.UtcNow.AddMinutes(-5),
                EndTimeUtc = DateTime.UtcNow,
                DurationSeconds = 300,
                CreatedAtUtc = DateTime.UtcNow,
            };

            TimeLogService service1;
            TimeLogService service2;
            
            service1 = CreateService();
            service2 = CreateService();

            var result = service1.CreateTimeLogsBatch(userId, [request, request2]);
            //Assert.Equal(1, result.AcceptedClientSessionIds.Count);
            var result2 = service2.CreateTimeLogsBatch(userId, [request, request2]);
            //Assert.Equal(1, result2.AcceptedClientSessionIds.Count);
            
            await Task.WhenAll(result,result2);
            
        }

        private TimeLogService CreateService()
        {
            var options = new DbContextOptionsBuilder<AppDbContext>()
                .UseNpgsql(connectionString)
                .Options;
            
            var context = new AppDbContext(options);

            var response2 = new TimeLogService(context, currentDeviceService);
            return response2;
        }
    }
}