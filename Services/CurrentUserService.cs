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

                if (context == null || context.User.Identity.IsAuthenticated == false)
                {
                    return null;
                }

                return null;
            }
        }
    }
}
