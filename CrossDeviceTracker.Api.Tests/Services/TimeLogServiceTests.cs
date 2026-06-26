using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Data;
using Xunit;
using Microsoft.EntityFrameworkCore;
using System;
using System.Threading.Tasks;

namespace CrossDeviceTracker.Api.Tests.Services
{
    public class TimeLogServiceTests
    {
        private readonly TimeLogService _service;

        private sealed class FakeCurrentDeviceService : ICurrentDeviceService
        {
            public Guid DeviceId { get; } = Guid.NewGuid();
        }

        public TimeLogServiceTests()
        {
            var options = new DbContextOptionsBuilder<AppDbContext>()
                .UseInMemoryDatabase(databaseName: Guid.NewGuid().ToString())
                .Options;

            var context = new AppDbContext(options);

            var currentDeviceService = new FakeCurrentDeviceService();

            _service = new TimeLogService(
                context,
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
    }
}