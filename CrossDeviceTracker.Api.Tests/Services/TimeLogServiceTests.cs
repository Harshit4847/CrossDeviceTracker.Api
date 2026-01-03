using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Services;
using CrossDeviceTracker.Api.Data;
using Xunit;
using System.Collections.Generic;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.InMemory;
using System;

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
        public void GetTimeLogsForUser_ShouldReturnEmptyList()
        {
            // Arrange
            Guid userId = Guid.NewGuid();

            // Act
            var result = _service.GetTimeLogsForUser(userId, null, null);

            // Assert
            Assert.NotNull(result);
            Assert.Empty(result.Items);
        }

        [Fact]
        public void GetTimeLogsForUser_ShouldReturnListOfTimeLogResponse()
        {
            // Arrange
            Guid userId = Guid.NewGuid();

            // Act
            var result = _service.GetTimeLogsForUser(userId, null, null);

            // Assert
            Assert.IsType<List<TimeLogResponse>>(result.Items);
        }
    }
}