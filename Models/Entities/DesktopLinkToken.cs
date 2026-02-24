namespace CrossDeviceTracker.Api.Models.Entities
{
    public sealed class DesktopLinkToken
    {
        private DesktopLinkToken() { }

        public Guid UserId { get; private set; }

        public User User{ get; private set; } 

        public byte[] TokenHash { get; private set; } 

        public DateTimeOffset ExpiresAt { get; private set; }

        public DateTimeOffset CreatedAt { get; private set; }

        public bool IsUsed { get; private set; }
    }
}
