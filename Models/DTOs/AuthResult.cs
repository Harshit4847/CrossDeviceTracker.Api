namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class AuthResult
    {
        public bool IsSuccess { get; set; }

        public string? AccessToken { get; set; } 

        public Guid? UserId { get; set; }

        public string? Email { get; set; }

        public string? ErrorMessage { get; set; }
    }
}
