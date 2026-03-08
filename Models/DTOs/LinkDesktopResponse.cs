namespace CrossDeviceTracker.Api.Models.DTOs
{
    public sealed class LinkDesktopResponse
    {
        public string DeviceJwt { get; }

        public LinkDesktopResponse(string deviceJwt)
        {
            DeviceJwt = deviceJwt;
        }
    }
}
