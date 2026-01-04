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

            var existingDevice = _context.Devices
                .FirstOrDefault(d =>d.UserId == request.UserId && d.Id == request.DeviceId);

            if (existingDevice == null)
            {
                var entity = new Device
                {
                    Id = request.DeviceId,
                    UserId = request.UserId,
                    DeviceName = request.DeviceName,
                    Platform = request.Platform,
                    CreatedAt = DateTime.UtcNow,
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
            else
            {

                var response = new DeviceResponse
                {
                    Id = existingDevice.Id,
                    UserId = existingDevice.UserId,
                    DeviceName = existingDevice.DeviceName,
                    Platform = existingDevice.Platform,
                    CreatedAt = existingDevice.CreatedAt
                };

                return response;
            }
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