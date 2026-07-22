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
        private readonly AppDbContext _context;
        private readonly IConfiguration _configuration;
        private readonly IDeviceJwtService _deviceJwtService;

        public DeviceService(AppDbContext context, IConfiguration configuration, IDeviceJwtService deviceJwtService)
        {
            _context = context;
            _configuration = configuration;
            _deviceJwtService = deviceJwtService;
        }

        public RegisterDeviceResponse CreateDevice(Guid UserId, CreateDeviceRequest request)
        {
            Device device;
            bool wasCreated;

            if (!string.IsNullOrWhiteSpace(request.InstallationId))
            {
                var existingDevice = _context.Devices
                    .SingleOrDefault(x =>
                        x.UserId == UserId &&
                        x.InstallationId == request.InstallationId);

                if (existingDevice != null)
                {
                    device = existingDevice;
                    wasCreated = false;
                }
                else
                {
                    device = new Device
                    {
                        Id = Guid.NewGuid(),
                        UserId = UserId,
                        DeviceName = request.DeviceName,
                        Platform = request.Platform,
                        InstallationId = request.InstallationId,
                        TokenVersion = 1,
                        IsRevoked = false,
                        LastDataSyncAt = null,
                        CreatedAt = DateTime.UtcNow,
                    };

                    _context.Devices.Add(device);
                    _context.SaveChanges();
                    wasCreated = true;
                }
            }
            else
            {
                device = new Device
                {
                    Id = Guid.NewGuid(),
                    UserId = UserId,
                    DeviceName = request.DeviceName,
                    Platform = request.Platform,
                    InstallationId = request.InstallationId,
                    TokenVersion = 1,
                    IsRevoked = false,
                    LastDataSyncAt = null,
                    CreatedAt = DateTime.UtcNow,
                };

                _context.Devices.Add(device);
                _context.SaveChanges();
                wasCreated = true;
            }

            var deviceJwt = _deviceJwtService.GenerateDeviceJwt(
                device.Id,
                device.UserId,
                device.TokenVersion);

            Console.WriteLine("DEBUG: Device JWT generated");

            return new RegisterDeviceResponse
            {
                DeviceId = device.Id,
                DeviceJwt = deviceJwt,
                WasCreated = wasCreated,
                DeviceName = device.DeviceName,
                Platform = device.Platform
            };
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
                    InstallationId = device.InstallationId,
                    TokenVersion = device.TokenVersion,
                    IsRevoked = device.IsRevoked,
                    LastDataSyncAt = device.LastDataSyncAt,
                    CreatedAt = device.CreatedAt

                });
            }

            return responses;
        }

        private static DeviceResponse MapToDeviceResponse(Device device)
        {
            return new DeviceResponse
            {
                Id = device.Id,
                UserId = device.UserId,
                DeviceName = device.DeviceName,
                Platform = device.Platform,
                InstallationId = device.InstallationId,
                TokenVersion = device.TokenVersion,
                IsRevoked = device.IsRevoked,
                LastDataSyncAt = device.LastDataSyncAt,
                CreatedAt = device.CreatedAt
            };
        }

        public async Task<GenerateDesktopLinkTokenResponse> GenerateDesktopLinkTokenAsync(Guid userId)
        {
            // Invalidate existing unused token before creating new one
            var existingToken = await _context.DesktopLinkTokens
                .Where(t => t.UserId == userId && !t.IsUsed)
                .FirstOrDefaultAsync();

            if (existingToken != null)
            {
                existingToken.MarkAsUsed();
            }

            var expiryMinutes = _configuration.GetValue<int>("DesktopLinkToken:ExpiryMinutes", 10);
            var expiresAt = DateTimeOffset.UtcNow.AddMinutes(expiryMinutes);

            // generate 32 random bytes (the raw token)
            var rawToken = RandomNumberGenerator.GetBytes(32);

            // hash it (SHA256) - this is what you store in DB
            var tokenHash = SHA256.HashData(rawToken);

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

        public async Task<LinkDesktopResponse> LinkDesktopAsync(LinkDesktopCommand command)
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
                .SingleOrDefaultAsync(t => t.TokenHash == hashBytes);

            if (tokendb == null)
            {
                throw new UnauthorizedException("Invalid linking token");
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
                InstallationId = null,
                TokenVersion = 1,
                IsRevoked = false,
                LastDataSyncAt = null,
                CreatedAt = DateTime.UtcNow
            };

            _context.Devices.Add(device);
            tokendb.MarkAsUsed();
            await _context.SaveChangesAsync();

            //working on JWT
            var claims = new[]
            {
                new Claim(JwtRegisteredClaimNames.Sub, device.UserId.ToString()),

                new Claim("user_id", device.UserId.ToString()),
                new Claim("device_id", device.Id.ToString()),
            };

            var jwtKey = _configuration.GetValue<string>("Jwt:Key");
            if(string.IsNullOrWhiteSpace(jwtKey))
            {
                throw new InvalidOperationException("JWT signing key is not configured.");
            }
            var keyBytes = Encoding.UTF8.GetBytes(jwtKey);


            var securityKey = new SymmetricSecurityKey(keyBytes);

            var credentials = new SigningCredentials(
                securityKey,
                SecurityAlgorithms.HmacSha256
            );

            var deviceJwtExpiryDays = _configuration.GetValue<int>("DeviceJwt:ExpiryDays", 365);

            var tokenDescriptor = new JwtSecurityToken(
                issuer: _configuration["Jwt:Issuer"],
                audience: _configuration["Jwt:Audience"],
                claims: claims,
                expires: DateTime.UtcNow.AddDays(deviceJwtExpiryDays),
                signingCredentials: credentials
            );

            var handler = new JwtSecurityTokenHandler();
            var tokenString = handler.WriteToken(tokenDescriptor);

            return new LinkDesktopResponse(tokenString, device.Id);
        }
    }
}
