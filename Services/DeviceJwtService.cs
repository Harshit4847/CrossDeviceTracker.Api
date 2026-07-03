using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace CrossDeviceTracker.Api.Services
{
    public class DeviceJwtService : IDeviceJwtService
    {
        private readonly IConfiguration _configuration;

        public DeviceJwtService(IConfiguration configuration)
        {
            _configuration = configuration;
        }

        public string GenerateDeviceJwt(Guid deviceId, Guid userId, int tokenVersion)
        {
            var key = _configuration["Jwt:Key"];
            var issuer = _configuration["Jwt:Issuer"];
            var audience = _configuration["Jwt:Audience"];
            var expiryDays = _configuration.GetValue<int>("DeviceJwt:ExpiryDays", 365);

            if (key == null || issuer == null || audience == null)
            {
                throw new InvalidOperationException("JWT configuration is missing.");
            }

            var securityKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key));
            var credentials = new SigningCredentials(securityKey, SecurityAlgorithms.HmacSha256);

            var claims = new List<Claim>
            {
                new Claim("device_id", deviceId.ToString()),
                new Claim("user_id", userId.ToString()),
                new Claim("token_version", tokenVersion.ToString()),
                new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
            };

            var token = new JwtSecurityToken(
                issuer: issuer,
                audience: audience,
                claims: claims,
                expires: DateTime.UtcNow.AddDays(expiryDays),
                signingCredentials: credentials
            );

            return new JwtSecurityTokenHandler().WriteToken(token);
        }
    }
}
