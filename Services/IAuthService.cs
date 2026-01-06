using CrossDeviceTracker.Api.Models.DTOs;

namespace CrossDeviceTracker.Api.Services
{
    public interface IAuthService
    {
        public Task<AuthResult> RegisterAsync(string email, string password);
        public Task<AuthResult> LoginAsync(string email, string password);
    }
}
