# CrossDeviceTracker.Api

A backend API for tracking screen time and foreground application usage across multiple devices. Built with ASP.NET Core (.NET 10.0), Entity Framework Core, and PostgreSQL.

The system measures active foreground app engagement time on desktop and mobile devices and synchronizes usage data to a centralized backend — similar to how Digital Wellbeing works, but across devices.

## Features

- **Dual JWT Authentication** — User JWT for website/API access; Device JWT for device-originated data (time logs)
- **Desktop Device Linking** — One-time cryptographic link tokens (SHA-256 hashed, time-limited) to securely pair desktop apps
- **Mobile Device Registration** — Android devices register via User JWT with `InstallationId` for idempotent pairing
- **Device Identity from JWT Claims** — `DeviceId` is extracted from Device JWT claims, never from request bodies
- **Device Management** — Register, list, and manage multiple devices per user
- **Time Log Tracking** — Record per-app screen time entries with app name, start time, and duration
- **Cursor-Based Pagination** — Efficient paginated retrieval of time logs using `StartTime` keyset
- **Global Exception Handling** — Custom middleware for consistent error responses (401, 403, 500)
- **Swagger/OpenAPI** — Interactive API documentation available in all environments

## Technology Stack

| Component | Technology |
|---|---|
| Framework | .NET 10.0 |
| Database | PostgreSQL (via Npgsql 10.0.0) |
| ORM | Entity Framework Core 10.0.1 |
| Auth | JWT Bearer (Microsoft.AspNetCore.Authentication.JwtBearer 10.0.1) |
| API Docs | Swashbuckle.AspNetCore 10.1.0 |
| Testing | xUnit 2.9.3, EF Core InMemory |

## Project Structure

```
CrossDeviceTracker.Api/
├── Controllers/
│   ├── AuthController.cs         # Registration & login
│   ├── DevicesController.cs      # Device CRUD & desktop linking
│   └── TimeLogsController.cs     # Time log creation & retrieval
├── Services/
│   ├── AuthService.cs            # Auth business logic
│   ├── DeviceService.cs          # Device & link token logic
│   ├── TimeLogService.cs         # Time log business logic
│   ├── CurrentUserService.cs     # Extracts UserId from JWT claims
│   └── CurrentDeviceService.cs   # Extracts DeviceId from Device JWT claims
├── Models/
│   ├── Entities/                 # EF Core entities (User, Device, TimeLog, DesktopLinkToken)
│   ├── DTOs/                     # Request/response models
│   └── Commands/                 # Command models (LinkDesktopCommand)
├── Data/
│   └── AppDbContext.cs           # EF Core DbContext
├── Exceptions/
│   ├── ExceptionHandlingMiddleware.cs
│   ├── UnauthorizedException.cs
│   └── ForbiddenException.cs
├── Migrations/                   # EF Core migrations
├── CrossDeviceTracker.Api.Tests/ # Unit tests
├── Program.cs                    # Application entry point
├── appsettings.json              # Configuration template
└── DESIGN.md                     # Full system design document
```

## Prerequisites

- [.NET 10.0 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)
- [PostgreSQL](https://www.postgresql.org/download/) 12+
- IDE: Visual Studio 2025, VS Code, or JetBrains Rider

## Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/Harshit4847/CrossDeviceTracker.Api.git
   cd CrossDeviceTracker.Api
   ```

2. **Configure settings**

   Copy the template and fill in your values:
   ```bash
   cp appsettings.Development.json.template appsettings.Development.json
   ```

   Update `appsettings.Development.json`:
   ```json
   {
     "ConnectionStrings": {
       "DefaultConnection": "Host=localhost;Port=5432;Database=ScreenTimeTrackerDB;Username=postgres;Password=YOUR_PASSWORD"
     },
     "Jwt": {
       "Key": "YOUR_JWT_SECRET_KEY_HERE_MIN_32_CHARS",
       "Issuer": "CrossDeviceTrackerAPI",
       "Audience": "CrossDeviceTrackerClient",
       "ExpiryMinutes": 60
     }
   }
   ```

3. **Restore packages**
   ```bash
   dotnet restore
   ```

4. **Apply database migrations**
   ```bash
   dotnet ef database update
   ```

5. **Run the application**
   ```bash
   dotnet run
   ```

The API will be available at the URLs displayed in the console output. Swagger UI is accessible at `/swagger`.

## API Endpoints

### Auth (`/api/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | No | Register a new user (email + password) |
| POST | `/api/auth/token` | No | Login and receive a User JWT access token |

### Devices (`/api/devices`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/devices` | User JWT | List all devices for the authenticated user |
| POST | `/api/devices` | User JWT | Register a new device (mobile — uses `InstallationId`) |
| POST | `/api/devices/link-token` | User JWT | Generate a one-time desktop link token |
| POST | `/api/devices/link` | User JWT | Link a desktop app using a link token; returns a Device JWT (requires authentication and validates token ownership) |

### Time Logs (`/api/timelogs`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/timelogs` | Device JWT | Create a single time log entry (DeviceId extracted from JWT claims) |
| POST | `/api/timelogs/batch` | Device JWT | Create multiple time log entries in a single request |
| GET | `/api/timelogs` | JWT | Get time logs (supports `?limit=` and `?cursor=` query params) |

## Database

The project uses Entity Framework Core with PostgreSQL. Four main entities:

- **User** — `Id`, `Email`, `PasswordHash`, `CreatedAt`
- **Device** — `Id`, `UserId`, `DeviceName`, `Platform`, `CreatedAt`
- **TimeLog** — `Id`, `UserId`, `DeviceId`, `AppName`, `StartTime`, `EndTime`, `DurationSeconds`, `CreatedAt`
- **DesktopLinkToken** — `Id`, `UserId`, `TokenHash` (SHA-256), `ExpiresAt`, `IsUsed`, `CreatedAt`

### Authentication Model

The system uses two types of JWTs:

| Token Type | Issued To | Claims | Used For |
|------------|-----------|--------|----------|
| User JWT | Website / Mobile app | `user_id` | User-level operations (device management, analytics) |
| Device JWT | Desktop / Mobile device | `device_id`, `user_id`, `token_version` | Device-originated data (time log submission) |

Device identity is always derived from JWT claims — the API never accepts `DeviceId` from request bodies.

### Migration Commands

```bash
# Create a new migration
dotnet ef migrations add MigrationName

# Apply migrations
dotnet ef database update

# Revert to a previous migration
dotnet ef database update PreviousMigrationName
```

## Device Linking Flows

### Desktop Linking (Link Token)

1. User logs in on the website and generates a one-time link token (`POST /api/devices/link-token`)
2. Backend generates a cryptographically secure random token (32 bytes), stores its SHA-256 hash, and returns the raw token as URL-safe Base64
3. User pastes the token into the desktop app
4. Desktop app sends the token + device name + platform to `POST /api/devices/link`
5. Backend validates the token (hash match, not expired, not used), creates a device record, and returns a Device JWT

### Mobile Registration

1. User logs in on the mobile app and receives a User JWT (`POST /api/auth/token`)
2. Mobile app registers the device (`POST /api/devices`) with `DeviceName`, `Platform`, and `InstallationId`
3. Backend creates a device record (or reuses existing one for the same `UserId` + `InstallationId`)

## Development

Swagger is enabled in all environments and accessible at `/swagger`. Development-specific settings go in `appsettings.Development.json`.

```bash
# Run in development
dotnet run

# Run with a specific launch profile
dotnet run --launch-profile https
```

### Related Projects

- [CrossDeviceTracker.Desktop](https://github.com/Harshit4847/CrossDeviceTracker.Desktop) — Windows desktop client (foreground window tracking, offline-first sync)

## Testing

Unit tests are located in `CrossDeviceTracker.Api.Tests/` and use xUnit with EF Core InMemory provider.

```bash
dotnet test
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Author

**Harshit Yadav**
- GitHub: [@Harshit4847](https://github.com/Harshit4847)
- Email: official.harshit@outlook.com