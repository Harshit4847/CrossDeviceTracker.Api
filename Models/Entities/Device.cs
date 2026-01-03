namespace CrossDeviceTracker.Api.Models.Entities
{
    public class Device
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string DeviceName { get; set; } = string.Empty;
        public string Platform { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
    }
}
