using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Exceptions;
using CrossDeviceTracker.Api.Models.Commands;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using CrossDeviceTracker.Api;


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

        async Task<LinkDesktopResponse> LinkDesktopAsync(LinkDesktopCommand command)
        {
            var token = command.LinkToken;
            //restroring peding

            token = token.Replace('-', '+').Replace('_', '/');
            int remainder = token.Length % 4;

            if (remainder == 2)
            {
                token += "==";
            }
            else if (remainder == 3)
            {
                token += "=";
            }
            else if (remainder == 1)
            {
                throw new UnauthorizedException("Invalid linking token");
            }

            byte[] decodedBytes;

            try
            {
                decodedBytes = Convert.FromBase64String(token);
            }
            catch
            {
                throw new UnauthorizedException("Invalid linking token");
            }

            if (decodedBytes.Length != 32)
            {
                throw new UnauthorizedException("Invalid linking token");
            }

            byte[] hashBytes = SHA256.HashData(decodedBytes);

            var tokendb = await _context.DesktopLinkTokens
                .Where(t => t.TokenHash == hashBytes)
                .FirstOrDefaultAsync();

            if (tokendb == null)
            {
                throw new UnauthorizedAccessException("Invalid linking token");
            }

            if (tokendb.IsUsed)
            {
                throw new UnauthorizedException("Invalid linking token");
            }

            if (tokendb.ExpiresAt < DateTimeOffset.UtcNow)
            {
                throw new UnauthorizedException("Invalid linking token");
            }



            var device = new Device
            {
                Id = Guid.NewGuid(),
                UserId = tokendb.UserId,
                DeviceName = command.DeviceName,
                Platform = command.Platform,
                CreatedAt = DateTime.UtcNow
            };

            _context.Devices.Add(device);
            tokendb.MarkAsUsed();
            await _context.SaveChangesAsync();

            //working on JWT
            var claims = new[]
            {
            new Claim("device_id", device.Id.ToString()),
            new Claim("user_id", device.UserId.ToString()),
            };

            var jwtKey = _configuration["Jwt:Key"];
            var keyBytes = Encoding.UTF8.GetBytes(jwtKey);

            var securityKey = new SymmetricSecurityKey(keyBytes);

            var credentials = new SigningCredentials(
                securityKey,
                SecurityAlgorithms.HmacSha256
            );

            var tokenDescriptor = new JwtSecurityToken(
                issuer: _configuration["Jwt:Issuer"],
                audience: _configuration["Jwt:Audience"],
                claims: claims,
                expires: DateTime.UtcNow.AddMinutes(
                    _configuration.GetValue<int>("Jwt:ExpiryMinutes")
                ),
                signingCredentials: credentials
            );

            var handler = new JwtSecurityTokenHandler();
            var tokenString = handler.WriteToken(tokenDescriptor);

            return new LinkDesktopResponse
            {
                DeviceJwt = tokenString
            };
        }
    }
}
