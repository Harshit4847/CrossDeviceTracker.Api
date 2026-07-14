using CrossDeviceTracker.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace CrossDeviceTracker.Api.Services
{
    public class AppNormalizationService : IAppNormalizationService
    {
        private readonly AppDbContext _context;

        public AppNormalizationService(AppDbContext context)
        {
            _context = context;
        }

        public async Task<string> NormalizeAppNameAsync(string appName, string platform)
        {
            if (string.IsNullOrWhiteSpace(appName))
            {
                return appName;
            }

            // Look up the alias in the database
            var alias = await _context.AppAliases
                .FirstOrDefaultAsync(a => a.Alias == appName && a.Platform == platform);

            // If found, return the canonical name
            if (alias != null)
            {
                return alias.CanonicalName;
            }

            // If not found, return the original app name
            return appName;
        }
    }
}
