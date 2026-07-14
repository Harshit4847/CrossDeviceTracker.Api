namespace CrossDeviceTracker.Api.Models.Entities
{
    public class AppAlias
    {
        public Guid Id { get; set; }
        public string CanonicalName { get; set; } = string.Empty;
        public string Alias { get; set; } = string.Empty;
        public string Platform { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
    }
}
