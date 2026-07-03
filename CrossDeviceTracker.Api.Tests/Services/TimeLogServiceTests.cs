using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Data;
using Xunit;
using Microsoft.EntityFrameworkCore;
using System;
using System.Threading.Tasks;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.Extensions.Configuration;

namespace CrossDeviceTracker.Api.Tests.Services
{
    public class TimeLogServiceTests
    {
        private readonly TimeLogService _service;
        private readonly AppDbContext _context;

        private sealed class FakeCurrentDeviceService : ICurrentDeviceService
        {
            public Guid DeviceId { get; } = Guid.NewGuid();
        }

        private sealed class FakeDeviceJwtService : IDeviceJwtService
        {
            public string GenerateDeviceJwt(Guid deviceId, Guid userId, int tokenVersion)
            {
                return "fake-jwt-token";
            }
        }

        public TimeLogServiceTests()
        {
            var options = new DbContextOptionsBuilder<AppDbContext>()
                .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
                .Options;

            _context = new AppDbContext(options);

            var currentDeviceService = new FakeCurrentDeviceService();

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
        public void CreateDevice_ShouldPopulateTrackingFields()
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
    }
}