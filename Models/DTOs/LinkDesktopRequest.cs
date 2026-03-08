using System.ComponentModel.DataAnnotations;

namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class LinkDesktopRequest
    {

        [Required]
        [MinLength(20)]
        [MaxLength(200)]
        public string LinkToken { get; set; } 

        [Required]
        [MinLength(1)]
        [MaxLength(100)]
        public string DeviceName { get; set; } 

        [Required]
        [MinLength(1)]
        [MaxLength(20)]
        public string Platform { get; set; } 
    }
}
