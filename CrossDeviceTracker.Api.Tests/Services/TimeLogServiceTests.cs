using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Data;
using Xunit;
using System.Collections.Generic;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.InMemory;
using System;
using System.Threading.Tasks;

namespace CrossDeviceTracker.Api.Tests.Services
{
    public class TimeLogServiceTests
    {
        private readonly TimeLogService _service;

        public TimeLogServiceTests()
        {
            var options = new DbContextOptionsBuilder<AppDbContext>()
                .UseInMemoryDatabase(databaseName: "TestDatabase")
                .Options;
            
            var context = new AppDbContext(options);
            _service = new TimeLogService(context);
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