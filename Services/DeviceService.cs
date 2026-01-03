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

        public DeviceResponse CreateDevice(CreateDeviceRequest request)
        {
            var entity = new Device
            {
                Id = Guid.NewGuid(),
                UserId = request.UserId,
                DeviceName = request.DeviceName,
                Platform = request.Platform,
                CreatedAt = DateTime.UtcNow
            };

            _context.Devices.Add(entity);
            _context.SaveChanges();

            var response = new DeviceResponse
            {

                Id = entity.Id,
                UserId = entity.UserId,
                DeviceName = entity.DeviceName,
                Platform = entity.Platform,
                CreatedAt = entity.CreatedAt
            };

            

            return response;
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