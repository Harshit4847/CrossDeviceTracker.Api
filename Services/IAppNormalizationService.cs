namespace CrossDeviceTracker.Api.Services
{
    public interface IAppNormalizationService
    {
        Task<string> NormalizeAppNameAsync(string appName, string platform);
    }
}
