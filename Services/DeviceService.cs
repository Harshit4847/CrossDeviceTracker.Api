using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.EntityFrameworkCore;

namespace CrossDeviceTracker.Api.Services
{
    public class DeviceService : IDeviceService
    {
        public readonly AppDbContext _context;

        public DeviceService(AppDbContext context)
        {
            _context = context;
        }

        public DeviceResult CreateDevice(Guid UserId, CreateDeviceRequest request)
        {

            DeviceResult result = new DeviceResult();
            var response = new DeviceResponse();

                var entity = new Device
                {
                    Id = Guid.NewGuid(),
                    UserId = UserId,
                    DeviceName = request.DeviceName,
                    Platform = request.Platform,
                    CreatedAt = DateTime.UtcNow,
                };

                _context.Devices.Add(entity);
                _context.SaveChanges();

                response.Platform = entity.Platform;
                response.Id = entity.Id;
                response.UserId = entity.UserId;
                response.DeviceName = entity.DeviceName;
                response.CreatedAt = entity.CreatedAt;

            result.Device = response;
            return result;
        }

        public List<DeviceResponse> GetDevicesForUser(Guid userId)
        {
            var devices = _context.Devices.AsNoTracking()
                .Where(x => x.UserId == userId)
                .OrderByDescending(x => x.CreatedAt)
                .ToList();

            List<DeviceResponse> responses = new List<DeviceResponse>();

            foreach (var device in devices)
            {
                responses.Add(new DeviceResponse
                {
                    Id = device.Id,
                    UserId = device.UserId,
                    DeviceName = device.DeviceName,
                    Platform = device.Platform,
                    CreatedAt = device.CreatedAt

                });
            }

            return responses;
        }
    }
}