using System;
using System.Collections.Generic;

namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class PaginatedTimeLogsResponse
    {
        public List<TimeLogResponse> Items { get; set; } = new List<TimeLogResponse>();

        public string? NextCursor { get; set; }
        
        public bool HasMore { get; set; } = false;
    }
}
