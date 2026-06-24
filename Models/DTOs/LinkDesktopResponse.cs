namespace CrossDeviceTracker.Api.Models.DTOs
{
    public sealed class LinkDesktopResponse
    {
        public string DeviceJwt { get; }
        public Guid DeviceId { get; }

        public LinkDesktopResponse(string deviceJwt, Guid deviceId)
        {
            DeviceJwt = deviceJwt;
            DeviceId = deviceId;
        }
    }
}
