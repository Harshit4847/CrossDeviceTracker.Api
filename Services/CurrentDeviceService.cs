using CrossDeviceTracker.Api.Exceptions;

namespace CrossDeviceTracker.Api.Services
{
    public class CurrentDeviceService : ICurrentDeviceService
    {
        private readonly IHttpContextAccessor _contextAccessor;

        public CurrentDeviceService(IHttpContextAccessor contextAccessor)
        {
            _contextAccessor = contextAccessor;
        }

        public Guid DeviceId
        {
            get
            {
                var context = _contextAccessor.HttpContext;

                if (context?.User?.Identity?.IsAuthenticated != true)
                {
                    throw new UnauthorizedException("User is not authenticated.");
                }

                var deviceIdClaim = context.User.FindFirst("device_id")?.Value;

                if (string.IsNullOrWhiteSpace(deviceIdClaim))
                {
                    throw new UnauthorizedException("DeviceId claim is missing.");
                }

                if (!Guid.TryParse(deviceIdClaim, out var deviceId))
                {
                    throw new UnauthorizedException("Invalid DeviceId claim.");
                }

                return deviceId;
            }
        }
    }
}
