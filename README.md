# CrossDeviceTracker.Api

[![CodeFactor](https://www.codefactor.io/repository/github/harshit4847/crossdevicetracker.api/badge)](https://www.codefactor.io/repository/github/harshit4847/crossdevicetracker.api)

> A backend API for tracking screen time and foreground application usage across multiple devices. Built with ASP.NET Core (.NET 10.0), Entity Framework Core, and PostgreSQL.

The system measures active foreground app engagement time on desktop and mobile devices and synchronizes usage data to a centralized backend — similar to how Digital Wellbeing works, but across devices.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Database](#database)
- [Device Linking](#device-linking)
- [Configuration](#configuration)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

```bash
git clone https://github.com/Harshit4847/CrossDeviceTracker.Api.git
cd CrossDeviceTracker.Api
cp appsettings.Development.json.template appsettings.Development.json
dotnet restore
dotnet ef database update
dotnet run
```

API available at the console output URLs. Swagger UI at `/swagger`.

**Prerequisites:** [.NET 10.0 SDK](https://dotnet.microsoft.com/download/dotnet/10.0), [PostgreSQL](https://www.postgresql.org/download/) 12+

---

## Features

| Feature | Description |
|---------|-------------|
| **Dual JWT Auth** | User JWT for website/API access; Device JWT for device data submission |
| **Desktop Linking** | One-time cryptographic link tokens (SHA-256, time-limited) for secure pairing |
| **Mobile Registration** | Android devices register via User JWT with `InstallationId` for idempotent pairing |
| **Device Identity from Claims** | `DeviceId` extracted from JWT claims — never from request bodies |
| **Time Log Tracking** | Per-app screen time entries with app name, start time, and duration |
| **Cursor Pagination** | Efficient keyset pagination using `StartTime` |
| **Global Error Handling** | Custom middleware for consistent 401/403/500 responses |
| **Swagger/OpenAPI** | Interactive API documentation in all environments |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | .NET 10.0 |
| Database | PostgreSQL (Npgsql 10.0.0) |
| ORM | Entity Framework Core 10.0.1 |
| Auth | JWT Bearer (Microsoft.AspNetCore.Authentication.JwtBearer 10.0.1) |
| API Docs | Swashbuckle.AspNetCore 10.1.0 |
| Testing | xUnit 2.9.3, EF Core InMemory |

---

## API Endpoints

### Auth

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | No | Register a new user |
| POST | `/api/auth/token` | No | Login and receive a User JWT |

### Devices

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/devices` | User JWT | List all devices for the authenticated user |
| POST | `/api/devices` | User JWT | Register a new device (mobile — uses `InstallationId`) |
| POST | `/api/devices/link-token` | User JWT | Generate a one-time desktop link token |
| POST | `/api/devices/link` | User JWT | Link a desktop app using a link token; returns a Device JWT |

### Time Logs

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/timelogs` | Device JWT | Create a single time log entry |
| POST | `/api/timelogs/batch` | Device JWT | Create multiple time log entries |
| GET | `/api/timelogs` | JWT | Get time logs (supports `?limit=` and `?cursor=`) |

### Dashboard

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/dashboard/summary` | User JWT | Today/yesterday/week/month totals, device count, app count, most used app |
| GET | `/api/dashboard/apps` | User JWT | App usage breakdown (filters: `from`, `to`, `deviceId`, `platform`) |
| GET | `/api/dashboard/devices` | User JWT | Device usage breakdown with optional date filters |
| GET | `/api/dashboard/timeline` | User JWT | Chronological timeline of sessions |

### Analytics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/analytics/daily` | User JWT | Daily usage chart data |
| GET | `/api/analytics/weekly` | User JWT | Weekly usage chart data |
| GET | `/api/analytics/monthly` | User JWT | Monthly usage chart data |
| GET | `/api/analytics/hourly` | User JWT | Hourly distribution chart data |

> **Note:** Dashboard and analytics endpoints provide pre-aggregated data — the recommended approach for client apps. All endpoints support optional `from`/`to` date filters (UTC).

---

## Project Structure

```
CrossDeviceTracker.Api/
├── Controllers/            # API endpoints
│   ├── AuthController.cs
│   ├── DevicesController.cs
│   ├── TimeLogsController.cs
│   ├── DashboardController.cs
│   └── AnalyticsController.cs
├── Services/               # Business logic
│   ├── AuthService.cs
│   ├── DeviceService.cs
│   ├── TimeLogService.cs
│   ├── CurrentUserService.cs
│   └── CurrentDeviceService.cs
├── Models/
│   ├── Entities/           # EF Core entities
│   ├── DTOs/               # Request/response models
│   └── Commands/           # Command models
├── Data/AppDbContext.cs    # EF Core DbContext
├── Exceptions/             # Custom exceptions & middleware
├── Migrations/             # EF Core migrations
├── Program.cs              # Entry point
└── appsettings.json        # Configuration
```

---

## Database

Five core entities:

| Entity | Key Fields |
|--------|------------|
| **User** | `Id`, `Email`, `PasswordHash`, `CreatedAt` |
| **Device** | `Id`, `UserId`, `DeviceName`, `Platform`, `InstallationId`, `TokenVersion`, `IsRevoked`, `LastDataSyncAt`, `CreatedAt` |
| **TimeLog** | `Id`, `UserId`, `DeviceId`, `AppName`, `StartTime`, `EndTime`, `DurationSeconds`, `CreatedAt` |
| **DesktopLinkToken** | `Id`, `UserId`, `TokenHash` (SHA-256), `ExpiresAt`, `IsUsed`, `CreatedAt` |
| **AppAlias** | `Id`, `CanonicalName`, `Alias`, `Platform`, `CreatedAt` |

### Authentication Model

| Token Type | Issued To | Claims | Purpose |
|------------|-----------|--------|---------|
| User JWT | Website / Mobile app | `user_id` | Device management, analytics |
| Device JWT | Desktop / Mobile device | `device_id`, `user_id`, `token_version` | Time log submission |

### Migration Commands

```bash
dotnet ef migrations add MigrationName   # Create migration
dotnet ef database update                 # Apply migrations
dotnet ef database update PreviousMigrationName  # Revert
```

---

## Device Linking

### Desktop (Link Token)

1. User generates a link token via `POST /api/devices/link-token`
2. Backend creates a SHA-256 hashed, time-limited token and returns it as URL-safe Base64
3. User pastes token into desktop app
4. Desktop sends token + device info to `POST /api/devices/link`
5. Backend validates, creates device record, returns a Device JWT

### Mobile (InstallationId)

1. User logs in on mobile app and receives a User JWT
2. Mobile registers device via `POST /api/devices` with `DeviceName`, `Platform`, `InstallationId`
3. Backend creates device record (or reuses existing one for same `UserId` + `InstallationId`)

---

## Configuration

```bash
cp appsettings.Development.json.template appsettings.Development.json
```

Required settings in `appsettings.Development.json`:

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

> For production hosting options (environment variables, appsettings.Production.json), see [README-Configuration.md](README-Configuration.md).

---

## Related Projects

- [CrossDeviceTracker.Desktop](https://github.com/Harshit4847/CrossDeviceTracker.Desktop) — Windows desktop client (foreground window tracking, offline-first sync)

---

## Testing

```bash
dotnet test
```

Unit tests are in `CrossDeviceTracker.Api.Tests/` using xUnit with EF Core InMemory provider.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Author

**Harshit Yadav**
- GitHub: [@Harshit4847](https://github.com/Harshit4847)
- Email: official.harshit@outlook.com
