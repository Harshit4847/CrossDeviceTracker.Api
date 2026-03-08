namespace CrossDeviceTracker.Api.Models.Commands
{
    public sealed class LinkDesktopCommand
    {
        public string LinkToken { get; }
        public string DeviceName { get; }
        public string Platform { get; }

        public LinkDesktopCommand(string linkToken, string deviceName, string platform)
        {
            LinkToken = linkToken;
            DeviceName = deviceName;
            Platform = platform;
        }
    }
}
