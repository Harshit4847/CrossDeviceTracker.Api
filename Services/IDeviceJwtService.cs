namespace CrossDeviceTracker.Api.Services
{
    public interface IDeviceJwtService
    {
        string GenerateDeviceJwt(Guid deviceId, Guid userId, int tokenVersion);
    }
}
