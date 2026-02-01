using Microsoft.AspNetCore.Mvc;
using CrossDeviceTracker.Api.Services;
using Microsoft.AspNetCore.Authorization;
using CrossDeviceTracker.Api.Models.DTOs;
using System.Threading.Tasks;

namespace CrossDeviceTracker.Api.Controllers
{
    [ApiController]
    [Route("api/auth")]

    public class AuthController : ControllerBase
    {
        private readonly IAuthService _authService;
        public AuthController(IAuthService authService)
        {
            _authService = authService;
        }

        [HttpPost("register")]
        public async Task<IActionResult> Register([FromBody] RegisterRequest request)
        {
            if (request == null)
            {
                return BadRequest("Request body is null");
            }

            if (string.IsNullOrWhiteSpace(request.Email))
            {
                return BadRequest("Email is required");
            }

            if (string.IsNullOrWhiteSpace(request.Password))
            {
                return BadRequest("Password is required");
            }

            var response = await _authService.RegisterAsync(request.Email, request.Password);
            if (!response.IsSuccess)
            {
                return BadRequest(response.ErrorMessage);
            }

            return CreatedAtAction(nameof(Register), new { }, new
            {
                userId = response.UserId,
                email = response.Email
            });
        }

        [HttpPost("token")]
        public async Task<IActionResult> Login ([FromBody] LoginRequest request)
        {
            if (request == null)
            {
                return BadRequest("Request body is null");
            }
            if (string.IsNullOrWhiteSpace(request.Email))
            {
                return BadRequest("Email is required");
            }
            if (string.IsNullOrWhiteSpace(request.Password))
            {
                return BadRequest("Password is required");
            }
            var response = await _authService.LoginAsync(request.Email, request.Password);
            if (response.IsSuccess == false)
            {
                return Unauthorized("Invalid Email or password");
            }
            return Ok(new
            {
                accessToken = response.AccessToken,
                email = response.Email
            });
        }
    }
}
