namespace CrossDeviceTracker.Api.Services
{
    public interface ICurrentUserService
    {
        Guid? UserId { get; }
    }
}
