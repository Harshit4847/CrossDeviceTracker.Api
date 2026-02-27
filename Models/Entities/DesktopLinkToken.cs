namespace CrossDeviceTracker.Api.Models.Entities
{
    public sealed class DesktopLinkToken
    {
        private DesktopLinkToken() { } // For EF Core

        public DesktopLinkToken(Guid userId, byte[] tokenHash, DateTimeOffset expiresAt)
        {
            if (userId == Guid.Empty)
                throw new ArgumentException("UserId cannot be empty.", nameof(userId));

            if (tokenHash == null)
                throw new ArgumentNullException(nameof(tokenHash));

            if (tokenHash.Length != 32)
                throw new ArgumentException("TokenHash must be 32 bytes (SHA256).", nameof(tokenHash));

            Id = Guid.NewGuid();
            UserId = userId;
            TokenHash = tokenHash;
            ExpiresAt = expiresAt;
            CreatedAt = DateTimeOffset.UtcNow;
            IsUsed = false;
        }

        public Guid Id { get; private set; }

        public Guid UserId { get; private set; }

        public User? User { get; private set; }

        public byte[] TokenHash { get; private set; }

        public DateTimeOffset ExpiresAt { get; private set; }

        public DateTimeOffset CreatedAt { get; private set; }

        public bool IsUsed { get; private set; }

        public void MarkAsUsed()
        {
            if (IsUsed)
                throw new InvalidOperationException("Token has already been used.");

            IsUsed = true;
        }
    }
}