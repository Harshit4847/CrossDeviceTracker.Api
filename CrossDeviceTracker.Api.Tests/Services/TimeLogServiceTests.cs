using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using Xunit;

namespace CrossDeviceTracker.Api.Tests.Services
{
    public class TimeLogServiceTests
    {
        private readonly TimeLogService _service;

        public TimeLogServiceTests()
        {
            _service = new TimeLogService();
        }

        [Fact]
        public void GetTimeLogsForUser_ShouldReturnEmptyList()
        {
            // Arrange
            int userId = 1;

            // Act
            var result = _service.GetTimeLogsForUser(userId);

            // Assert
            Assert.NotNull(result);
            Assert.Empty(result);
        }

        [Fact]
        public void GetTimeLogsForUser_ShouldReturnListOfTimeLogResponse()
        {
            // Arrange
            int userId = 1;

            // Act
            var result = _service.GetTimeLogsForUser(userId);

            // Assert
            Assert.IsType<List<TimeLogResponse>>(result);
        }
    }
}