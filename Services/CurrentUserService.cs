using System.Security.Claims;
using System.IdentityModel.Tokens.Jwt;
using CrossDeviceTracker.Api.Exceptions;

namespace CrossDeviceTracker.Api.Services
{
    public class CurrentUserService : ICurrentUserService
    {
        private readonly IHttpContextAccessor _contextAccessor;

        public CurrentUserService(IHttpContextAccessor contextAccessor)
        {
            _contextAccessor = contextAccessor;
        }

        public Guid UserId
        {
            get
            {
                var context = _contextAccessor.HttpContext;

                if (context?.User?.Identity?.IsAuthenticated != true)
                {
                    throw new UnauthorizedException("User is not authenticated.");
                }

                var userIdClaim = context.User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value
                    ?? context.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

                if (string.IsNullOrWhiteSpace(userIdClaim))
                {
                    throw new UnauthorizedException("UserId claim is missing.");
                }

                if (!Guid.TryParse(userIdClaim, out var userId))
                {
                    throw new UnauthorizedException("Invalid UserId claim.");
                }

                return userId;
            }
        }
    }
}
