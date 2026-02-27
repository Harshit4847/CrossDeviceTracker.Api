namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class GenerateDesktopLinkTokenResponse
    {
        public string Token { get; set; } = string.Empty;
        public DateTimeOffset ExpiresAt { get; set; }
    }
}
