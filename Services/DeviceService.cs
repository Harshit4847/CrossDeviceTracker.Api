using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.Commands;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using System.Security.Cryptography;

namespace CrossDeviceTracker.Api.Services
{
    public class DeviceService : IDeviceService
    {
        public readonly AppDbContext _context;
        private readonly IConfiguration _configuration;

        public DeviceService(AppDbContext context, IConfiguration configuration)
        {
            _context = context;
            _configuration = configuration;
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

        public async Task<GenerateDesktopLinkTokenResponse> GenerateDesktopLinkTokenAsync(Guid userId)
        {
            // HERE is where you put those lines:
            var expiryMinutes = _configuration.GetValue<int>("DesktopLinkToken:ExpiryMinutes", 10);
            var expiresAt = DateTimeOffset.UtcNow.AddMinutes(expiryMinutes);

            // generate 32 random bytes (the raw token)
            var rawToken = RandomNumberGenerator.GetBytes(32);

            // hash it (SHA256) - this is what you store in DB
            var tokenHash = SHA256.HashData(rawToken);

            // optional: delete existing unused token(s) for this user to avoid unique constraint issues
            var existingUnused = await _context.DesktopLinkTokens
                .Where(t => t.UserId == userId && !t.IsUsed)
                .ToListAsync();

            if (existingUnused.Count > 0)
            {
                _context.DesktopLinkTokens.RemoveRange(existingUnused);
            }

            var entity = new DesktopLinkToken(userId, tokenHash, expiresAt);

            _context.DesktopLinkTokens.Add(entity);
            await _context.SaveChangesAsync();

            // return base64url string
            var token = Convert.ToBase64String(rawToken)
                .TrimEnd('=')
                .Replace('+', '-')
                .Replace('/', '_');

            return new GenerateDesktopLinkTokenResponse
            {
                Token = token,
                ExpiresAt = expiresAt
            };
        }

        Task<LinkDesktopRequest> LinkDesktopAsync(LinkDesktopCommand command)
        {

            return;
        }
    }
}
