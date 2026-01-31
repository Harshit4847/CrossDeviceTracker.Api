using System.Security.Claims;

namespace CrossDeviceTracker.Api.Services
{
    public class CurrentUserService : ICurrentUserService
    {
        private readonly IHttpContextAccessor _contextAccessor;

        public CurrentUserService (IHttpContextAccessor contextAccessor)
        {
            _contextAccessor = contextAccessor;
        }

        public Guid? UserId
        {
            get
            {
                var context = _contextAccessor.HttpContext;

                if (context?.User?.Identity?.IsAuthenticated != true)
                {
                    return null;
                }

                var userIdClaim = context.User.Claims
                    .FirstOrDefault(c => c.Type == ClaimTypes.NameIdentifier)
                    ?.Value;

                if (string.IsNullOrWhiteSpace(userIdClaim))
                {
                    return null;
                }

                if (!Guid.TryParse(userIdClaim, out var userId))
                {
                    return null;
                }

                return userId;
            }
        }
    }
}
