using System.Collections.Generic;

namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class AcceptedTimeLogsResponse
    {
        public List<string> AcceptedClientSessionIds { get; set; } = new();
    }
}
