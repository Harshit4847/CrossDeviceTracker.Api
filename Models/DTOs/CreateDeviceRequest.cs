using System.ComponentModel.DataAnnotations;

namespace CrossDeviceTracker.Api.Models.DTOs
{
    public class CreateDeviceRequest
    {
        [Required]
        [MinLength(1)]
        [MaxLength(100)]
        public string DeviceName { get; set; } 

        [Required]
        [MinLength(1)]
        [MaxLength(30)]
        public string Platform {  get; set; }

    }
}
