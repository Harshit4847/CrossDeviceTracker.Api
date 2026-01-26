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

                var sub = context.User.Claims
                    .FirstOrDefault(c => c.Type == "sub" || c.Type == ClaimTypes.NameIdentifier)
                    ?.Value;

                if (string.IsNullOrWhiteSpace(sub))
                {
                    return null;
                }

                if (!Guid.TryParse(sub, out var userId))
                {
                    return null;
                }

                return userId;
            }
        }
    }
}
