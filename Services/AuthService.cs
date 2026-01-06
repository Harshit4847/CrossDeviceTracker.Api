using CrossDeviceTracker.Api.Data;
using CrossDeviceTracker.Api.Models.DTOs;
using CrossDeviceTracker.Api.Models.Entities;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using System.IdentityModel.Tokens.Jwt;
using Microsoft.IdentityModel.Tokens;


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

            if (isUserExists) {

                result.IsSuccess = false;
                result.ErrorMessage = "User with this email already exists.";

            }
            else {

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

            if (user == null) {
                result.IsSuccess = false;
                result.ErrorMessage = "Email or password is invalid.";
            }
            else {


                var passwordVerificationResult = _passwordHasher.VerifyHashedPassword(user, user.PasswordHash, password);
                if (passwordVerificationResult == PasswordVerificationResult.Failed) {
                    result.IsSuccess = false;
                    result.ErrorMessage = "Email or password is invalid.";
                }
                else {
                    result.IsSuccess = true;
                    result.UserId = user.Id;
                    result.Email = user.Email;
                }
            }
            return result;
        }
    }
}
