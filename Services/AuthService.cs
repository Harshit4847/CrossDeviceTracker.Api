using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace CrossDeviceTracker.Api.Services
{
    public class AuthService : IAuthService
    {
        private readonly AppDbContext _context;
        private readonly IConfiguration _configuration;
        private readonly IPasswordHasher<User> _passwordHasher;

        public AuthService(AppDbContext context, IConfiguration configuration, IPasswordHasher<User> passwordHasher)
        {
            _context = context;
            _configuration = configuration;
            _passwordHasher = passwordHasher;
        }

        public async Task<AuthResult> RegisterAsync(string email, string password)
        {
            var isUserExists = await _context.Users.AnyAsync(u => u.Email == email);

            AuthResult result = new AuthResult();

            if (isUserExists)
            {
                result.IsSuccess = false;
                result.ErrorMessage = "User with this email already exists.";
            }
            else
            {
                var newUser = new User
                {
                    Email = email,
                    CreatedAt = DateTime.UtcNow,
                    Id = Guid.NewGuid()
                };
                newUser.PasswordHash = _passwordHasher.HashPassword(newUser, password);

                await _context.Users.AddAsync(newUser);
                await _context.SaveChangesAsync();

                result.IsSuccess = true;
                result.UserId = newUser.Id;
                result.Email = newUser.Email;
            }

            return result;
        }

        public async Task<AuthResult> LoginAsync(string email, string password)
        {
            var user = await _context.Users.FirstOrDefaultAsync(u => u.Email == email);
            AuthResult result = new AuthResult();

            if (user == null)
            {
                result.IsSuccess = false;
                result.ErrorMessage = "Email or password is invalid.";
            }
            else
            {
                var passwordVerificationResult = _passwordHasher.VerifyHashedPassword(user, user.PasswordHash, password);
                if (passwordVerificationResult == PasswordVerificationResult.Failed)
                {
                    result.IsSuccess = false;
                    result.ErrorMessage = "Email or password is invalid.";
                }
                else
                {
                    result.IsSuccess = true;
                    result.Email = user.Email;
                    result.AccessToken = GenerateJwtToken(user.Id, user.Email);
                }
            }

            return result;
        }

        private string GenerateJwtToken(Guid userId, string? email)
        {
            var key = _configuration["Jwt:Key"];
            var issuer = _configuration["Jwt:Issuer"];
            var audience = _configuration["Jwt:Audience"];
            var expiryMinutes = _configuration["Jwt:ExpiryMinutes"];

            if (key == null || issuer == null || audience == null || expiryMinutes == null)
            {
                throw new InvalidOperationException("JWT configuration is missing.");
            }

            var securityKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(key));
            var credentials = new SigningCredentials(securityKey, SecurityAlgorithms.HmacSha256);

            var claims = new List<Claim>
            {
                new Claim(JwtRegisteredClaimNames.Sub, userId.ToString()),
                new Claim(ClaimTypes.NameIdentifier, userId.ToString())

            };

            if (!string.IsNullOrWhiteSpace(email))
            {
                claims.Add(new Claim(JwtRegisteredClaimNames.Email, email));

            }

            if (!double.TryParse(expiryMinutes, out var minutes))
            {
                throw new InvalidOperationException("JWT expiry is invalid.");
            }

            var token = new JwtSecurityToken(
                issuer: issuer,
                audience: audience,
                claims: claims,
                expires: DateTime.UtcNow.AddMinutes(minutes),
                signingCredentials: credentials
            );

            return new JwtSecurityTokenHandler().WriteToken(token);
        }
    }
}
