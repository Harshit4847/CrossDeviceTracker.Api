# Cross Device Screen Time Tracker — Project Documentation

> **Author:** Harshit Yadav  
> **Last Updated:** March 3, 2026  
> **Version:** 1.0  
> **Repository:** [github.com/Harshit4847/CrossDeviceTracker.Api](https://github.com/Harshit4847/CrossDeviceTracker.Api)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [Technology Stack & Justifications](#4-technology-stack--justifications)
5. [High-Level Architecture](#5-high-level-architecture)
6. [Project Structure](#6-project-structure)
7. [Database Design](#7-database-design)
8. [Entity Design & Domain Rules](#8-entity-design--domain-rules)
9. [Authentication & Authorization](#9-authentication--authorization)
10. [Desktop Linking Flow](#10-desktop-linking-flow)
11. [API Endpoints](#11-api-endpoints)
12. [Service Layer Design](#12-service-layer-design)
13. [DTO & Command Patterns](#13-dto--command-patterns)
14. [Error Handling Strategy](#14-error-handling-strategy)
15. [Time Log Tracking & Sync Strategy](#15-time-log-tracking--sync-strategy)
16. [Pagination Strategy](#16-pagination-strategy)
17. [Security Decisions](#17-security-decisions)
18. [Configuration Management](#18-configuration-management)
19. [Testing Strategy](#19-testing-strategy)
20. [Deployment & Environments](#20-deployment--environments)
21. [Current Implementation Status](#21-current-implementation-status)
22. [Known Issues & Incomplete Work](#22-known-issues--incomplete-work)
23. [Future Roadmap](#23-future-roadmap)
24. [Design Decision Log](#24-design-decision-log)

---

## 1. Project Overview

The **Cross Device Screen Time Tracker** is a system that measures foreground application engagement time on desktop devices and synchronizes usage data to a centralized backend API. Users can register, link multiple devices (desktop, Android, Mac), and view aggregated screen-time analytics through a web dashboard.

The system is composed of three parts:

| Component | Technology | Role |
|-----------|-----------|------|
| **Backend API** | ASP.NET Core (.NET 10.0) | JWT auth, device linking, time log storage, validation |
| **Website** | (Planned) | User dashboard, analytics, device management |
| **Desktop App** | C# (Planned) | Foreground window tracking, local SQLite storage, sync to backend |

This document covers the **Backend API** — its design, architecture, decisions, and current state.

---

## 2. Problem Statement

Users today use multiple devices (desktop, phone, tablet) throughout the day. Existing screen-time tools (like Windows Screen Time or Android Digital Wellbeing) only track usage on a single device. There is no unified way to:

- See total screen time across all devices in one place
- Understand which apps consume the most attention across platforms
- Get engagement-based metrics (foreground app time) rather than raw uptime

This project solves that by providing a cross-device backend that aggregates time logs from multiple devices per user.

---

## 3. Goals & Non-Goals

### Goals

- Track **foreground app engagement time** (not background or uptime)
- Support **multiple devices per user** (desktop first, mobile later)
- Provide a **secure device-linking mechanism** (one-time tokens for desktop)
- Store all time logs centrally with **server-side validation**
- **Cursor-based pagination** for efficient time log retrieval
- **Offline-first** desktop client that syncs when connectivity is restored

### Non-Goals

- Not tracking background app time
- Not tracking pixel-level screen visibility
- Not building a content filter or parental control system
- Not supporting real-time streaming of tracking data (batch sync only)
- Not building mobile tracking apps in this phase

---

## 4. Technology Stack & Justifications

| Technology | Version | Why This Choice |
|-----------|---------|-----------------|
| **.NET 10.0** | 10.0 | Latest LTS-track release; excellent performance; same language (C#) as planned desktop app |
| **ASP.NET Core** | 10.0 | Mature, battle-tested web framework with built-in DI, middleware, authentication |
| **PostgreSQL** | 12+ | Open-source, robust RDBMS; supports partial unique indexes (critical for DesktopLinkToken constraint); excellent JSONB support for future analytics |
| **Npgsql.EntityFrameworkCore.PostgreSQL** | 10.0.0 | Official EF Core provider for PostgreSQL |
| **Entity Framework Core** | 10.0.1 | Code-first migrations, LINQ queries, strong typing; productive ORM for rapid development |
| **JWT (HMAC-SHA256)** | via `System.IdentityModel.Tokens.Jwt` 8.15.0 | Stateless authentication; no session store needed; works well with device authentication |
| **ASP.NET Core Identity PasswordHasher** | Built-in | Secure bcrypt-like password hashing with automatic salt; no need for a custom implementation |
| **Swashbuckle (Swagger)** | 10.1.0 | Auto-generated interactive API documentation for development and testing |
| **xUnit** | 2.9.3 | De facto standard for .NET unit testing |
| **EF Core InMemory** | 10.0.1 | Fast in-memory database provider for unit testing without a real database |

### Why Not Other Choices?

| Alternative | Why Not |
|------------|---------|
| **MongoDB** | Relational data (users → devices → time logs) maps naturally to SQL; partial unique indexes needed for token system |
| **SQLite (server-side)** | Not suitable for concurrent multi-user API; SQLite is used only in the desktop client for local storage |
| **Session-based auth** | Requires server-side session store; doesn't scale easily; JWT is better for device auth |
| **OAuth2 / External IdP** | Overengineered for this scope; email+password is sufficient; external providers add complexity |
| **gRPC** | REST is simpler for web dashboard consumption; gRPC would be relevant only for desktop↔API communication and adds complexity |

---

## 5. High-Level Architecture

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Website    │       │  Desktop App │       │  Mobile App  │
│   (React?)   │       │    (C#)      │       │  (Future)    │
└──────┬───────┘       └──────┬───────┘       └──────┬───────┘
       │                      │                      │
       │  User JWT            │  Device JWT          │  User JWT
       │                      │                      │
       ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    CrossDeviceTracker.Api                    │
│                     (ASP.NET Core 10.0)                      │
│                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  Auth    │  │   Devices    │  │     Time Logs         │  │
│  │Controller│  │  Controller  │  │    Controller          │  │
│  └────┬─────┘  └──────┬───────┘  └──────────┬────────────┘  │
│       │               │                     │                │
│  ┌────┴─────┐  ┌──────┴───────┐  ┌──────────┴────────────┐  │
│  │  Auth    │  │   Device     │  │     TimeLog            │  │
│  │ Service  │  │   Service    │  │     Service            │  │
│  └────┬─────┘  └──────┬───────┘  └──────────┬────────────┘  │
│       │               │                     │                │
│  ┌────┴───────────────┴─────────────────────┴────────────┐  │
│  │                    AppDbContext                         │  │
│  │              (Entity Framework Core)                    │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                    ┌───────▼───────┐
                    │  PostgreSQL   │
                    │   Database    │
                    └───────────────┘
```

### Request Pipeline

```
HTTP Request
    → CORS Middleware
    → Exception Handling Middleware (custom)
    → Authentication Middleware (JWT Bearer)
    → Authorization Middleware
    → Controller
    → Service Layer
    → DbContext → PostgreSQL
    → Response
```

---

## 6. Project Structure

```
CrossDeviceTracker.Api/
│
├── Controllers/                    # API endpoints (thin controllers)
│   ├── AuthController.cs           # POST /api/auth/register, POST /api/auth/token
│   ├── DevicesController.cs        # GET/POST /api/devices, link-token, link
│   └── TimeLogsController.cs       # GET/POST /api/timelogs
│
├── Services/                       # Business logic layer
│   ├── IAuthService.cs             # Auth interface
│   ├── AuthService.cs              # Registration, login, JWT generation
│   ├── IDeviceService.cs           # Device interface
│   ├── DeviceService.cs            # Device CRUD, desktop link token, linking
│   ├── ITimeLogService.cs          # TimeLog interface
│   ├── TimeLogService.cs           # Time log creation, paginated retrieval
│   ├── ICurrentUserService.cs      # Current user interface
│   └── CurrentUserService.cs       # Extracts UserId from JWT claims
│
├── Models/
│   ├── Entities/                   # EF Core database entities
│   │   ├── User.cs
│   │   ├── Device.cs
│   │   ├── TimeLog.cs
│   │   └── DesktopLinkToken.cs     # Sealed entity with domain invariants
│   ├── DTOs/                       # Data Transfer Objects (request/response)
│   │   ├── RegisterRequest.cs
│   │   ├── LoginRequest.cs
│   │   ├── AuthResult.cs
│   │   ├── CreateDeviceRequest.cs
│   │   ├── DeviceResponse.cs
│   │   ├── DeviceResult.cs
│   │   ├── CreateTimeLogRequest.cs
│   │   ├── TimeLogResponse.cs
│   │   ├── PaginatedTimeLogsResponse.cs
│   │   ├── GenerateDesktopLinkTokenResponse.cs
│   │   ├── LinkDesktopRequest.cs
│   │   ├── LinkDesktopResponse.cs
│   │   └── PairDeviceRequest.cs    # Placeholder
│   └── Commands/
│       └── LinkDesktopCommand.cs   # Immutable command object for desktop linking
│
├── Data/
│   └── AppDbContext.cs             # EF Core DbContext with Fluent API config
│
├── Exceptions/                     # Custom exception types + middleware
│   ├── ExceptionHandlingMiddleware.cs
│   ├── UnauthorizedException.cs    # Maps to 401
│   └── ForbiddenException.cs       # Maps to 403
│
├── Migrations/                     # EF Core database migrations
│   ├── InitialCreate
│   ├── AddUsersTable
│   └── AddDesktopLinkTokens
│
├── Properties/
│   └── launchSettings.json
│
├── CrossDeviceTracker.Api.Tests/   # Unit tests
│   └── Services/
│       └── TimeLogServiceTests.cs
│
├── Program.cs                      # Application entry point & DI configuration
├── appsettings.json                # Base config (empty secrets)
├── appsettings.Development.json.template
├── appsettings.Production.json.template
├── CrossDeviceTracker.Api.csproj
└── CrossDeviceTracker.Api.sln
```

### Design Decision: Folder Structure

The project follows a **layered architecture** (Controller → Service → Data) rather than vertical slices or Clean Architecture. This was chosen for:

- **Simplicity:** Small project, single bounded context
- **Familiarity:** Standard ASP.NET Core convention
- **Low ceremony:** No need for MediatR, repositories, or CQRS at this scale

If the project grows significantly, consider migrating to vertical slice architecture.

---

## 7. Database Design

### 7.1 Entity Relationship Diagram

```
┌──────────┐       ┌──────────────┐       ┌──────────────────┐
│  Users   │───1:N─│   Devices    │       │ DesktopLinkTokens│
│          │       │              │       │                  │
│ Id (PK)  │       │ Id (PK)      │       │ Id (PK)          │
│ Email    │       │ UserId (FK)  │       │ UserId (FK)      │
│ Password │───1:N─│ DeviceName   │       │ TokenHash        │
│  Hash    │   │   │ Platform     │       │ ExpiresAt        │
│ CreatedAt│   │   │ CreatedAt    │       │ CreatedAt        │
└──────────┘   │   └──────────────┘       │ IsUsed           │
               │                          └──────────────────┘
               │
               │   ┌──────────────┐
               └──▶│  TimeLogs    │
                   │              │
                   │ Id (PK)      │
                   │ UserId (FK)  │
                   │ DeviceId     │
                   │ AppName      │
                   │ StartTime    │
                   │ EndTime      │
                   │ DurationSecs │
                   │ CreatedAt    │
                   └──────────────┘
```

### 7.2 Tables & Columns

#### `users`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `Id` | `Guid` | PK | Generated by application |
| `Email` | `string(255)` | Required, Unique Index | User login identifier |
| `PasswordHash` | `string` | Required | Hashed via ASP.NET Core Identity PasswordHasher |
| `CreatedAt` | `DateTime` | — | UTC timestamp |

#### `devices`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `Id` | `Guid` | PK | Generated by application |
| `UserId` | `Guid` | FK → users, Cascade Delete | Owner of the device |
| `DeviceName` | `string(255)` | Required | Auto-detected or user-provided |
| `Platform` | `string(100)` | Required | e.g., "Windows", "Android", "macOS" |
| `CreatedAt` | `DateTime` | — | UTC timestamp |

#### `time_logs`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `Id` | `Guid` | PK | Generated by application |
| `UserId` | `Guid` | FK → users, Cascade Delete | Owner of the log |
| `DeviceId` | `Guid` | — | Which device generated this log |
| `AppName` | `string(255)` | Required | Foreground application name |
| `StartTime` | `DateTime` | Required | UTC start of usage block |
| `EndTime` | `DateTime` | Required | UTC end of usage block |
| `DurationSeconds` | `int` | Required | Server-computed: EndTime - StartTime |
| `CreatedAt` | `DateTime` | — | When the record was created on server |

#### `desktop_link_tokens`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `id` | `Guid` | PK | Generated inside entity constructor |
| `user_id` | `Guid` | FK → users, Cascade Delete | Token owner |
| `token_hash` | `byte[]` | Required, Unique Index | SHA256 hash of raw token |
| `expires_at` | `DateTimeOffset` | Required | Expiry timestamp |
| `created_at` | `DateTimeOffset` | Required | Creation timestamp |
| `is_used` | `bool` | Required, default false | Single-use flag |

**Special Index:** `UNIQUE(user_id) WHERE is_used = false` — PostgreSQL partial unique index ensuring only one unused token per user at any time.

### 7.3 Design Decisions

| Decision | Rationale |
|----------|-----------|
| **GUIDs for primary keys** | No sequential integer leakage; safe for distributed generation; prevents enumeration attacks |
| **Cascade delete from Users** | If a user is deleted, all their devices, logs, and tokens are removed |
| **`DeviceId` on TimeLogs is not a FK** | Allows flexibility — logs persist even if a device is later deleted; avoids cascading complications |
| **Snake_case column names for `desktop_link_tokens`** | Follows PostgreSQL naming convention; other tables use PascalCase (inconsistency to address later) |
| **`DateTimeOffset` for token timestamps** | More explicit timezone handling for short-lived security tokens; `DateTime` used elsewhere for simpler data |
| **Server computes `EndTime`** | `EndTime = StartTime + DurationSeconds` — client-provided duration is used but server calculates EndTime for consistency |

---

## 8. Entity Design & Domain Rules

### 8.1 User Entity

Simple anemic entity — no domain logic. Registration and login logic lives in `AuthService`.

```csharp
public class User
{
    public Guid Id { get; set; }
    public string Email { get; set; }
    public string PasswordHash { get; set; }
    public DateTime CreatedAt { get; set; }
}
```

### 8.2 Device Entity

Simple anemic entity.

```csharp
public class Device
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public string DeviceName { get; set; }
    public string Platform { get; set; }
    public DateTime CreatedAt { get; set; }
}
```

**Note:** The `Device` entity in the current implementation does not yet have `IsRevoked`, `TokenVersion`, or `LastDataSyncAt` fields described in the DESIGN.md. These are planned for future implementation (see [Section 22](#22-known-issues--incomplete-work)).

### 8.3 TimeLog Entity

Simple anemic entity.

```csharp
public class TimeLog
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public Guid DeviceId { get; set; }
    public string AppName { get; set; }
    public DateTime StartTime { get; set; }
    public DateTime EndTime { get; set; }
    public int DurationSeconds { get; set; }
    public DateTime CreatedAt { get; set; }
}
```

### 8.4 DesktopLinkToken Entity (Rich Domain Entity)

This is the **only entity with domain-driven design principles** applied. It is `sealed`, has constructor invariants, and enforces controlled state transitions.

**Key Design Characteristics:**

| Characteristic | Detail |
|---------------|--------|
| **Sealed class** | Prevents inheritance misuse |
| **Private parameterless constructor** | Required for EF Core materialization; not callable externally |
| **Public constructor with invariants** | Validates `userId ≠ Guid.Empty`, `tokenHash ≠ null`, `tokenHash.Length == 32` |
| **Private setters on all properties** | No external mutation allowed |
| **`MarkAsUsed()` method** | Single controlled state transition: Unused → Used (irreversible) |
| **`Id` generated in constructor** | Entity owns its identity from the moment of creation |
| **`CreatedAt` set in constructor** | Domain owns time, not the database |

**Invariants (enforced in entity):**
- UserId cannot be `Guid.Empty`
- TokenHash must be exactly 32 bytes (SHA256)
- Token can only be used once (`MarkAsUsed()` throws if already used)

**Policies (enforced in service layer):**
- Expiry duration (configured via `DesktopLinkToken:ExpiryMinutes`)
- One unused token per user (enforced by DB partial unique index + service logic)
- Token cleanup rules

---

## 9. Authentication & Authorization

### 9.1 Authentication Model

The system uses **two types of JWT tokens**:

| Token Type | Issued To | Contains | Used For |
|-----------|-----------|----------|----------|
| **User JWT** | Website users | `Sub` (UserId), `Email` | Web dashboard, device management, link token generation |
| **Device JWT** | Desktop applications | `DeviceId`, `UserId`, `TokenVersion` | Time log submission (planned) |

Currently, only **User JWT** is implemented.

### 9.2 User JWT Details

- **Algorithm:** HMAC-SHA256 (symmetric)
- **Issuer/Audience:** Configured in `appsettings.json` → `Jwt:Issuer`, `Jwt:Audience`
- **Expiry:** Configured via `Jwt:ExpiryMinutes` (default: 60 minutes)
- **Claims:**
  - `sub` (JwtRegisteredClaimNames.Sub) → UserId as string
  - `ClaimTypes.NameIdentifier` → UserId as string (redundant, for compatibility)
  - `email` (JwtRegisteredClaimNames.Email) → User's email

### 9.3 Password Hashing

Uses `Microsoft.AspNetCore.Identity.PasswordHasher<User>` which implements:
- PBKDF2 with HMAC-SHA256/SHA512
- Automatic salt generation
- Iteration count following current security recommendations
- Version-aware hash format (auto-upgrades on verification)

### 9.4 CurrentUserService

Extracts the authenticated user's ID from JWT claims. Registered as `Scoped` in DI.

**Claim Resolution Order:**
1. `JwtRegisteredClaimNames.Sub`
2. `ClaimTypes.NameIdentifier` (fallback)

Throws `UnauthorizedException` if:
- User is not authenticated
- UserId claim is missing
- UserId claim is not a valid GUID

### 9.5 Authorization Flow in Controllers

All protected endpoints use `[Authorize]` attribute. The flow is:

```
Request → JWT Bearer Middleware (validates token signature, expiry, issuer, audience)
        → Controller method
        → _currentUserService.UserId (extracts UserId from claims)
        → Service method (uses UserId for data scoping)
```

**Design Decision:** Controllers do an explicit `userId == null || userId == Guid.Empty` check before calling services. This is a defense-in-depth measure — `CurrentUserService` already throws on invalid state, but controllers add a safety net returning `401 Unauthorized`.

---

## 10. Desktop Linking Flow

### 10.1 Why a Linking Token?

Desktop apps cannot use OAuth redirect flows easily. Instead of asking users to type email+password into a desktop app (security risk), the system uses a **one-time link token** flow:

1. User logs into the website
2. Website calls `POST /api/devices/link-token` → gets a one-time token
3. User pastes token into the desktop app
4. Desktop app calls `POST /api/devices/link` with token + device info
5. Backend validates token, creates device, issues Device JWT
6. Desktop app stores Device JWT and uses it for all future communication

### 10.2 Token Generation (`POST /api/devices/link-token`)

**Implementation in `DeviceService.GenerateDesktopLinkTokenAsync`:**

1. Read expiry duration from config: `DesktopLinkToken:ExpiryMinutes` (default: 10)
2. Generate 32 cryptographically secure random bytes using `RandomNumberGenerator.GetBytes(32)`
3. Compute SHA256 hash of the raw bytes
4. Delete any existing unused tokens for the user (prevents unique constraint violation)
5. Create `DesktopLinkToken` entity with hash + expiry
6. Save to database
7. Return raw token as URL-safe Base64 (padding removed, `+` → `-`, `/` → `_`)

**Security Properties:**
- Raw token is returned to client exactly once and never stored on server
- Only the SHA256 hash is stored in the database
- If database is compromised, attacker cannot reconstruct raw tokens
- URL-safe Base64 encoding ensures safe copy-paste across platforms

### 10.3 Token Consumption (`POST /api/devices/link`) — Planned

**Designed flow (not yet fully implemented):**

1. Desktop sends: raw token + DeviceName + Platform
2. Backend decodes URL-safe Base64 → raw bytes
3. Computes SHA256 hash
4. Queries `DesktopLinkTokens` by hash
5. Validates: exists, not expired, not used
6. Calls `MarkAsUsed()` on entity
7. Creates new `Device` record
8. Generates Device JWT
9. Returns Device JWT to desktop app
10. All within a single database transaction

### 10.4 Concurrency Protection

| Scenario | Protection |
|----------|-----------|
| Two simultaneous token generation requests | Partial unique index `UNIQUE(user_id) WHERE is_used = false` prevents duplicates; existing unused tokens deleted first |
| Two simultaneous consumption of same token | `MarkAsUsed()` + transaction ensures only one succeeds |
| Race between generation and consumption | Transaction isolation handles this |

---

## 11. API Endpoints

### 11.1 Auth Endpoints

#### `POST /api/auth/register`

**Auth:** None  
**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```
**Success Response (201 Created):**
```json
{
  "userId": "guid",
  "email": "user@example.com"
}
```
**Error Responses:**
- `400 Bad Request` — Missing email/password, or email already exists

**Validation:**
- Email and password must be non-empty
- Duplicate email check in database

---

#### `POST /api/auth/token`

**Auth:** None  
**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```
**Success Response (200 OK):**
```json
{
  "accessToken": "eyJhbG...",
  "email": "user@example.com"
}
```
**Error Responses:**
- `400 Bad Request` — Missing email/password
- `401 Unauthorized` — Invalid credentials

**Design Decision:** The login endpoint is `POST /api/auth/token` (not `/login`) following OAuth2 convention where the token endpoint issues access tokens.

---

### 11.2 Device Endpoints

#### `GET /api/devices`

**Auth:** Bearer token (User JWT)  
**Response (200 OK):**
```json
[
  {
    "id": "guid",
    "userId": "guid",
    "deviceName": "My Desktop",
    "platform": "Windows",
    "createdAt": "2026-01-05T12:00:00Z"
  }
]
```
Returns all devices for the authenticated user, ordered by `CreatedAt` descending.

---

#### `POST /api/devices`

**Auth:** Bearer token (User JWT)  
**Request Body:**
```json
{
  "deviceName": "My Phone",
  "platform": "Android"
}
```
**Success Response (201 Created):** Returns the created device.

**Validation:**
- `DeviceName`: Required, 1–100 characters
- `Platform`: Required, 1–30 characters

---

#### `POST /api/devices/link-token`

**Auth:** Bearer token (User JWT)  
**Response (200 OK):**
```json
{
  "token": "base64url-encoded-token",
  "expiresAt": "2026-03-03T10:10:00+00:00"
}
```
Generates a one-time token for desktop linking. Previous unused tokens for the user are invalidated.

---

#### `POST /api/devices/link`

**Auth:** Bearer token (User JWT)  
**Status:** Endpoint stub exists but implementation is incomplete.

---

### 11.3 Time Log Endpoints

#### `POST /api/timelogs`

**Auth:** Bearer token (User JWT)  
**Request Body:**
```json
{
  "deviceId": "guid",
  "appName": "Visual Studio Code",
  "startTime": "2026-03-03T08:00:00Z",
  "durationSeconds": 3600
}
```
**Success Response (200 OK):**
```json
{
  "id": "guid",
  "userId": "guid",
  "deviceId": "guid",
  "appName": "Visual Studio Code",
  "startTime": "2026-03-03T08:00:00Z",
  "endTime": "2026-03-03T09:00:00Z",
  "durationSeconds": 3600,
  "createdAt": "2026-03-03T09:01:00Z"
}
```

**Validation (Controller level):**
- Request body must not be null
- UserId must be valid (from JWT)
- DeviceId must not be `Guid.Empty`
- AppName must not be empty
- StartTime must not be in the future
- DurationSeconds must be > 0

**Validation (Service level):**
- Device must belong to the authenticated user (`ForbiddenException` if not)

**Server Behavior:**
- `EndTime` is computed by server: `StartTime + DurationSeconds`
- `Id` is generated by server
- `CreatedAt` is set to `DateTime.UtcNow`

---

#### `GET /api/timelogs?limit={limit}&cursor={cursor}`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `limit` (optional, int) — Max items to return (default: 20, max: 50)
- `cursor` (optional, DateTime) — Return items with `StartTime < cursor`

**Response (200 OK):**
```json
{
  "items": [ /* TimeLogResponse[] */ ],
  "nextCursor": "2026-03-02T15:00:00Z",
  "hasMore": true
}
```

Uses **cursor-based pagination** (see [Section 16](#16-pagination-strategy)).

---

## 12. Service Layer Design

### 12.1 Design Philosophy

- **Controllers are thin:** Only responsible for HTTP concerns (reading request, returning status codes)
- **Services contain business logic:** Validation, data access, computation
- **Interfaces for all services:** Enables unit testing with mocks
- **Registered as Scoped:** One instance per HTTP request

### 12.2 Service Registration (in Program.cs)

```csharp
builder.Services.AddScoped<IAuthService, AuthService>();
builder.Services.AddScoped<IDeviceService, DeviceService>();
builder.Services.AddScoped<ITimeLogService, TimeLogService>();
builder.Services.AddScoped<ICurrentUserService, CurrentUserService>();
builder.Services.AddScoped<IPasswordHasher<User>, PasswordHasher<User>>();
```

### 12.3 AuthService

| Method | Behavior |
|--------|----------|
| `RegisterAsync(email, password)` | Checks email uniqueness → creates User with hashed password → returns `AuthResult` |
| `LoginAsync(email, password)` | Finds user by email → verifies password → generates JWT → returns `AuthResult` |
| `GenerateJwtToken(userId, email)` | Private method. Creates signed JWT with claims, reads config for key/issuer/audience/expiry |

**Design Decision:** `AuthResult` is a result DTO that carries both success data and error information. This avoids throwing exceptions for expected business failures (like duplicate email). The service returns a result object; the controller decides the HTTP status code.

### 12.4 DeviceService

| Method | Behavior |
|--------|----------|
| `CreateDevice(userId, request)` | Creates device entity → saves → returns `DeviceResult` |
| `GetDevicesForUser(userId)` | Queries devices with `AsNoTracking()` → maps to `DeviceResponse` list |
| `GenerateDesktopLinkTokenAsync(userId)` | Generates crypto token → hashes → stores hash → returns raw token |
| `LinkDesktopAsync(command)` | **Not yet implemented** |

### 12.5 TimeLogService

| Method | Behavior |
|--------|----------|
| `CreateTimeLog(userId, request)` | Validates device ownership → computes EndTime → saves → returns `TimeLogResponse` |
| `GetTimeLogsForUser(userId, limit, cursor)` | Cursor-based paginated query → returns `PaginatedTimeLogsResponse` |

**Design Decision:** `TimeLogService` uses two constants for pagination:
- `DefaultLimit = 20` — When no limit is specified
- `MaxLimit = 50` — Hard cap to prevent abuse

---

## 13. DTO & Command Patterns

### 13.1 Request DTOs

Used for deserializing incoming HTTP request bodies.

| DTO | Used By | Fields |
|-----|---------|--------|
| `RegisterRequest` | `POST /api/auth/register` | Email, Password |
| `LoginRequest` | `POST /api/auth/token` | Email, Password |
| `CreateDeviceRequest` | `POST /api/devices` | DeviceName (1-100), Platform (1-30) |
| `CreateTimeLogRequest` | `POST /api/timelogs` | DeviceId, AppName, StartTime, DurationSeconds |
| `LinkDesktopRequest` | `POST /api/devices/link` | LinkToken (20-200), DeviceName (1-100), Platform (1-20) |

**Design Decision:** Request DTOs use `DataAnnotations` attributes (`[Required]`, `[MinLength]`, `[MaxLength]`) for declarative validation. However, controllers also perform explicit null/empty checks before calling services — this is intentional belt-and-suspenders validation.

### 13.2 Response DTOs

Used for serializing outgoing HTTP response bodies.

| DTO | Contains |
|-----|----------|
| `AuthResult` | IsSuccess, AccessToken, UserId, Email, ErrorMessage |
| `DeviceResponse` | Id, UserId, DeviceName, Platform, CreatedAt |
| `DeviceResult` | Device (DeviceResponse), WasCreated |
| `TimeLogResponse` | Id, UserId, DeviceId, AppName, StartTime, EndTime, DurationSeconds, CreatedAt |
| `PaginatedTimeLogsResponse` | Items (List<TimeLogResponse>), NextCursor, HasMore |
| `GenerateDesktopLinkTokenResponse` | Token, ExpiresAt |
| `LinkDesktopResponse` | DeviceJwt (sealed class, constructor-only) |

### 13.3 Command Objects

| Command | Purpose |
|---------|---------|
| `LinkDesktopCommand` | Immutable command object for desktop linking. Has `LinkToken`, `DeviceName`, `Platform` — all set via constructor, no setters. Separates HTTP-layer request DTO from service-layer command. |

**Design Decision:** `LinkDesktopCommand` is `sealed` and immutable (constructor-only properties). This follows the Command pattern — the command is an explicit, validated instruction to the service layer, decoupled from the HTTP request shape.

---

## 14. Error Handling Strategy

### 14.1 Exception Handling Middleware

The `ExceptionHandlingMiddleware` is a custom ASP.NET Core middleware that catches exceptions globally and maps them to appropriate HTTP responses.

| Exception Type | HTTP Status | Response |
|---------------|-------------|----------|
| `UnauthorizedException` | `401 Unauthorized` | `{ "error": "message" }` |
| `ForbiddenException` | `403 Forbidden` | `{ "error": "message" }` |
| `Exception` (unhandled) | `500 Internal Server Error` | `{ "error": "An unexpected error occurred" }` |

**Design Decisions:**
- Custom exceptions (`UnauthorizedException`, `ForbiddenException`) are domain-specific and thrown by services
- The middleware logs unhandled exceptions to console for debugging
- Generic 500 error message hides internal details from clients (security)
- `UnauthorizedException` is `sealed` to prevent inheritance

### 14.2 Error Handling Layers

| Layer | Error Handling Approach |
|-------|----------------------|
| **Controller** | Explicit null/validation checks → returns `BadRequest`, `Unauthorized` |
| **Service** | Throws `ForbiddenException`, `UnauthorizedException`, `ArgumentException` |
| **CurrentUserService** | Throws `UnauthorizedException` for invalid/missing claims |
| **Middleware** | Catches all unhandled exceptions → returns structured JSON error |

### 14.3 Design Decision: Result Objects vs Exceptions

The project uses a **mixed approach**:
- **`AuthResult`** for expected business outcomes (login success/failure, register success/duplicate)
- **Exceptions** for truly exceptional/unauthorized situations

This hybrid approach means: controllers check `IsSuccess` on auth results but rely on exception middleware for device ownership violations.

---

## 15. Time Log Tracking & Sync Strategy

### 15.1 What Is Tracked

The system tracks **foreground application engagement time**:
- Time spent actively using a specific foreground application
- Only while the system is unlocked
- Only when the screen session is active

**Not tracked:** Background app time, pixel-level screen visibility, pure device uptime.

### 15.2 Time Block Model

Each time log represents a single engagement block:

| Field | Meaning |
|-------|---------|
| `AppName` | Name of the foreground application |
| `StartTime` | UTC timestamp when the block started |
| `EndTime` | UTC timestamp when the block ended (server-computed) |
| `DurationSeconds` | Client-reported duration |
| `DeviceId` | Which device produced this log |

### 15.3 Server-Side Validation

When a time log is created:

1. **Device ownership check:** The device must belong to the authenticated user
2. **StartTime validation:** Cannot be in the future
3. **DurationSeconds validation:** Must be > 0
4. **EndTime computation:** Server calculates `EndTime = StartTime + DurationSeconds`

**Design Decision:** The server computes `EndTime` rather than trusting the client. The client sends `StartTime` + `DurationSeconds`, and the server derives `EndTime`. This follows the principle: **never trust client-computed timestamps for derived values**.

### 15.4 Sync Strategy (Desktop → Backend)

**Planned implementation (per DESIGN.md):**
- Desktop app stores time blocks locally in SQLite
- Logs are sent in small batches (e.g., 100 records)
- Each batch is processed atomically
- Success → mark as Sent, update `LastDataSyncAt`
- Validation error → mark as Failed, continue with next chunk
- Network error → keep as Pending, retry later

---

## 16. Pagination Strategy

### 16.1 Why Cursor-Based Pagination

The time logs endpoint uses **cursor-based pagination** instead of offset-based (`skip/take`):

| Feature | Offset-Based | Cursor-Based (chosen) |
|---------|-------------|----------------------|
| Consistency with new inserts | Duplicates/skips on page boundaries | Stable — always returns next items after cursor |
| Performance | `OFFSET` is O(n) in PostgreSQL | Indexed column seek is O(log n) |
| Suitability for real-time data | Poor (data shifts between pages) | Excellent (time-ordered data) |

### 16.2 Implementation

```
GET /api/timelogs?limit=20&cursor=2026-03-02T15:00:00Z
```

**Query logic:**
```sql
SELECT * FROM time_logs
WHERE user_id = @userId
  AND (@cursor IS NULL OR start_time < @cursor)
ORDER BY start_time DESC
LIMIT @limit + 1  -- fetch one extra to determine HasMore
```

- Fetches `limit + 1` records
- If count > limit → `HasMore = true`, last item is the cursor
- `NextCursor` = `StartTime` of the last item in the current page
- Client passes `NextCursor` as `cursor` parameter for the next page

### 16.3 Limits

- **Default limit:** 20
- **Maximum limit:** 50
- If client requests > 50, it is capped to 50

---

## 17. Security Decisions

### 17.1 Summary of Security Principles

| Principle | Implementation |
|-----------|---------------|
| **Never trust client duration** | Server computes `EndTime` from `StartTime + DurationSeconds` |
| **Never trust client identity** | All endpoints validate UserId from JWT, then verify against DB |
| **Hash all temporary tokens** | Desktop link tokens are SHA256-hashed; raw token never stored |
| **Use GUIDs for identifiers** | Prevents sequential enumeration attacks |
| **Server DB is authority** | JWT is verified against database state (token version, revocation) |
| **Generic error messages** | Invalid/expired/used tokens all return same "Invalid linking token" message |
| **No sensitive data in logs** | Connection strings are logged for debugging (should be removed in production) |

### 17.2 Token Security

- **Raw desktop link tokens:** Returned once, never stored, 32 bytes of cryptographic randomness
- **SHA256 hashing:** Hash stored in DB; raw token not recoverable
- **URL-safe Base64 encoding:** Safe for copy-paste across platforms
- **Short-lived:** Configurable expiry (default 10 minutes)
- **Single-use:** `MarkAsUsed()` is irreversible; enforced at entity level and DB level

### 17.3 CORS Configuration

Currently configured as **AllowAll** (any origin, any header, any method):

```csharp
policy.AllowAnyOrigin()
      .AllowAnyHeader()
      .AllowAnyMethod();
```

> **Warning:** This is acceptable for development but must be restricted in production to only allow the frontend domain.

### 17.4 HTTPS

`UseHttpsRedirection()` is commented out in `Program.cs`. In production, HTTPS should be enforced either at the application level or via a reverse proxy (e.g., Azure App Service handles this automatically).

---

## 18. Configuration Management

### 18.1 Configuration Files

| File | Purpose | In Git? |
|------|---------|---------|
| `appsettings.json` | Base config with empty secrets | Yes |
| `appsettings.Development.json.template` | Template for local development | Yes |
| `appsettings.Development.json` | Actual local dev config | No (gitignored) |
| `appsettings.Production.json.template` | Template for production | Yes |
| `appsettings.Production.json` | Actual production config | No (gitignored) |

### 18.2 Configuration Keys

```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Host=...;Database=...;Username=...;Password=..."
  },
  "Jwt": {
    "Key": "minimum-32-character-secret",
    "Issuer": "CrossDeviceTrackerAPI",
    "Audience": "CrossDeviceTrackerClient",
    "ExpiryMinutes": 60
  },
  "DesktopLinkToken": {
    "ExpiryMinutes": 10
  }
}
```

### 18.3 Environment Detection

The application reads `ASPNETCORE_ENVIRONMENT` to determine the environment:
- **Development:** Loads `appsettings.Development.json`, verbose logging
- **Production:** Loads `appsettings.Production.json`, minimal logging

The current `Program.cs` logs the environment name and connection string details at startup (should be removed for production deployments).

### 18.4 Production Deployment Options

1. **Environment Variables (Recommended):**
   ```
   ConnectionStrings__DefaultConnection=...
   Jwt__Key=...
   Jwt__Issuer=...
   Jwt__Audience=...
   ```
2. **Azure App Service Configuration:** Set values in Application Settings
3. **`appsettings.Production.json`:** File-based (never commit to Git)

---

## 19. Testing Strategy

### 19.1 Current Test Coverage

The project has a test project at `CrossDeviceTracker.Api.Tests/` with initial unit tests for `TimeLogService`:

| Test | Validates |
|------|----------|
| `GetTimeLogsForUser_ShouldReturnEmptyList` | Empty result for new user |
| `GetTimeLogsForUser_ShouldReturnListOfTimeLogResponse` | Correct return type (`PaginatedTimeLogsResponse`) |

### 19.2 Test Infrastructure

- **Framework:** xUnit 2.9.3
- **Database:** EF Core InMemory provider (fast, no external dependencies)
- **Pattern:** Arrange-Act-Assert

### 19.3 Testing Gaps (to be addressed)

| Area | Missing Tests |
|------|--------------|
| `AuthService` | Register (success, duplicate email), Login (success, wrong password, non-existent user) |
| `DeviceService` | CreateDevice, GetDevicesForUser, GenerateDesktopLinkToken |
| `TimeLogService` | CreateTimeLog (success, invalid device, future start time), pagination edge cases |
| `CurrentUserService` | Missing claims, invalid GUID, unauthenticated user |
| `DesktopLinkToken` | Constructor invariants, MarkAsUsed(), double-use prevention |
| **Integration tests** | Full HTTP pipeline tests with `WebApplicationFactory` |
| **Controller tests** | Validation behavior, status code mapping |

---

## 20. Deployment & Environments

### 20.1 Target Framework

- **.NET 10.0** (as specified in `.csproj`)
- Publish profile exists for **Azure App Service** (Zip Deploy)

### 20.2 Publish Profiles

The project includes a publish profile for Azure:
- `crossdevicetracker-api-hy - Zip Deploy.pubxml`

### 20.3 Database Migrations

Migrations are managed via EF Core CLI:

```bash
# Create a new migration
dotnet ef migrations add MigrationName

# Apply migrations to database
dotnet ef database update

# Revert to a specific migration
dotnet ef database update PreviousMigrationName
```

**Migration History:**
1. `20260104061907_InitialCreate` — Initial tables (Devices, TimeLogs)
2. `20260105121728_AddUsersTable` — Users table with auth support
3. `20260227080159_AddDesktopLinkTokens` — Desktop link tokens with partial unique index

---

## 21. Current Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| User registration | Done | Email + password, duplicate check |
| User login + JWT | Done | HMAC-SHA256, configurable expiry |
| Device creation (mobile path) | Done | POST /api/devices |
| List user devices | Done | GET /api/devices |
| Desktop link token generation | Done | Crypto-secure, SHA256 hashed |
| Desktop link token consumption | **Incomplete** | Endpoint stub exists, `LinkDesktopAsync` not implemented |
| Time log creation | Done | Server-computed EndTime, device ownership validation |
| Time log retrieval (paginated) | Done | Cursor-based pagination |
| Device JWT issuance | **Not started** | Designed but not implemented |
| Device revocation | **Not started** | `IsRevoked`, `TokenVersion` not on Device entity |
| Batch time log sync | **Not started** | Single log creation only |
| Exception handling middleware | Done | 401, 403, 500 mapping |
| CORS | Done (dev mode) | AllowAll — needs restriction for production |
| Swagger documentation | Done | Available in all environments |
| Unit tests | Partial | Only TimeLogService basic tests |

---

## 22. Known Issues & Incomplete Work

### 22.1 Code Issues

1. **`DevicesController.LinkDesktopRequest` method doesn't compile:**
   - `LinkDesktopAsync()` is called with no arguments but the interface requires a `LinkDesktopCommand`
   - Response handling is incomplete (missing closing brace and return)

2. **`DeviceService.LinkDesktopAsync` has a placeholder body:**
   - Returns `return;` in a `Task<LinkDesktopRequest>` method — does not compile

3. **Connection string logged at startup:**
   - `Program.cs` logs the full connection string value, which is a security concern for production

4. **`IDeviceService.LinkDesktopAsync` return type mismatch:**
   - Interface declares `Task<LinkDesktopRequest>` but should likely return `Task<LinkDesktopResponse>`

### 22.2 Missing Features vs DESIGN.md

| Designed Feature | Gap |
|-----------------|-----|
| `Device.IsRevoked` field | Not in entity |
| `Device.TokenVersion` field | Not in entity |
| `Device.LastDataSyncAt` field | Not in entity |
| Device JWT (separate from User JWT) | Not implemented |
| Token revocation (increment TokenVersion) | Not implemented |
| Constant-time hash comparison for tokens | Not implemented (using EF query) |
| Batch time log submission | Not implemented (single log only) |
| Duration tolerance validation | Not implemented |
| Time drift validation | Not implemented |
| Extreme duration check | Not implemented |

### 22.3 Naming Inconsistencies

- `desktop_link_tokens` uses snake_case column names; other tables use PascalCase
- `DeviceService._context` is declared `public readonly` instead of `private readonly`

---

## 23. Future Roadmap

### Phase 1: Complete Desktop Linking
- [ ] Implement `LinkDesktopAsync` in `DeviceService`
- [ ] Add `IsRevoked`, `TokenVersion`, `LastDataSyncAt` to `Device` entity
- [ ] Create EF Core migration for new Device fields
- [ ] Issue Device JWT on successful desktop link
- [ ] Add constant-time hash comparison for token validation

### Phase 2: Device Authentication & Revocation
- [ ] Create Device JWT validation middleware
- [ ] Implement device revocation endpoint
- [ ] Implement "logout from all devices" (TokenVersion increment)
- [ ] Add device status check endpoint (for desktop app startup)

### Phase 3: Batch Sync
- [ ] Add batch time log creation endpoint (`POST /api/timelogs/batch`)
- [ ] Implement server-side duration recalculation and tolerance check
- [ ] Add `LastDataSyncAt` update on successful sync
- [ ] Implement extreme duration validation

### Phase 4: Testing
- [ ] Full unit test coverage for all services
- [ ] Integration tests with `WebApplicationFactory`
- [ ] DesktopLinkToken entity invariant tests
- [ ] Controller validation behavior tests

### Phase 5: Production Hardening
- [ ] Restrict CORS to frontend domain
- [ ] Enable HTTPS redirection
- [ ] Remove connection string logging
- [ ] Add structured logging (Serilog)
- [ ] Add rate limiting on auth endpoints
- [ ] Add health check endpoint
- [ ] Token cleanup background job (remove expired/used tokens)

### Phase 6: Website Frontend
- [ ] User dashboard with screen time analytics
- [ ] Device management UI
- [ ] Desktop link token generation UI
- [ ] Charts/graphs for daily/weekly usage

### Phase 7: Desktop Application
- [ ] Foreground window tracking (Win32 API)
- [ ] System lock/unlock detection
- [ ] Local SQLite storage
- [ ] Chunked sync to backend
- [ ] Auto-start with Windows
- [ ] System tray UI

---

## 24. Design Decision Log

A chronological record of key design decisions and their rationale.

| # | Date | Decision | Alternatives Considered | Rationale |
|---|------|----------|------------------------|-----------|
| 1 | Jan 4, 2026 | Use PostgreSQL as the database | SQLite, MongoDB, SQL Server | PostgreSQL supports partial unique indexes (critical for token system), is free, and has excellent EF Core support |
| 2 | Jan 4, 2026 | Use GUIDs for all primary keys | Auto-increment integers | Prevents enumeration attacks, allows client-side ID generation, no central sequence bottleneck |
| 3 | Jan 4, 2026 | Layered architecture (Controller → Service → DbContext) | Clean Architecture, Vertical Slices, CQRS | Simplest approach for small project; avoids unnecessary abstraction layers (no Repository pattern — EF Core DbContext is already a UoW/Repository) |
| 4 | Jan 5, 2026 | JWT Bearer auth with HMAC-SHA256 | Session-based auth, OAuth2, RSA-signed JWTs | Stateless, works for both user and device auth, simple symmetric key management for single-server deployment |
| 5 | Jan 5, 2026 | ASP.NET Core Identity PasswordHasher | bcrypt (BCrypt.Net), Argon2 | Built-in, well-maintained, auto-upgrades hash algorithm, no external dependency |
| 6 | Jan 5, 2026 | Scoped DI lifetime for services | Transient, Singleton | One service instance per request matches DbContext lifetime (also Scoped); prevents concurrency issues |
| 7 | Feb 27, 2026 | Desktop link tokens with SHA256 hash storage | Store raw tokens, use shorter tokens with DB lookup | Hash-only storage means DB compromise doesn't leak valid tokens; 32-byte crypto random provides 256-bit entropy |
| 8 | Feb 27, 2026 | Sealed DesktopLinkToken entity with constructor invariants | Anemic entity like others | This entity has complex lifecycle rules (single-use, expiry) that benefit from DDD-style enforcement; other entities are simple enough for anemic style |
| 9 | Feb 27, 2026 | Partial unique index for one-unused-token-per-user | Application-level check only | DB constraint prevents race conditions that service-level checks cannot catch |
| 10 | Feb 27, 2026 | URL-safe Base64 for token encoding | Hex encoding, standard Base64 | Shorter than hex, safe for copy-paste and URL transport, no padding issues |
| 11 | — | Cursor-based pagination for time logs | Offset-based (skip/take) | Time logs are time-ordered and frequently inserted; cursor pagination is stable and performant with an indexed column |
| 12 | — | Server computes EndTime from StartTime + Duration | Trust client-provided EndTime | Client clock may be wrong or manipulated; server derivation ensures consistency |
| 13 | — | Custom exception middleware instead of built-in ProblemDetails | UseExceptionHandler, ProblemDetails | Custom middleware gives fine-grained control over error response format; simpler to understand |
| 14 | — | Mixed result-objects (AuthResult) and exceptions (ForbiddenException) | All exceptions, all result objects | Auth failures are expected business outcomes (result objects); ownership violations are exceptional (exceptions). Pragmatic hybrid. |
| 15 | — | No repository pattern (services use DbContext directly) | Repository + UoW pattern | EF Core DbContext IS already a repository + unit of work. Adding another layer would be pure abstraction without benefit at this scale. |

---

### Update: Device Authentication & Android Device Registration Design

During recent design discussions, the device authentication strategy for different client platforms was clarified and refined.

#### Desktop Authentication

Desktop applications will authenticate using the **link-token flow**.
A user generates a one-time linking token from the website, which is then entered into the desktop client. The backend validates the token, creates a new device entry, and issues a **Device JWT** to the desktop client. This token will be used for all future communication with the API.

#### Android Authentication Strategy

Unlike desktop clients, Android applications can present a login screen. Therefore, Android devices will follow a **two-step authentication flow**:

1. The user logs in using email and password (`/api/auth/token`) and receives a **User JWT**.
2. The Android app registers the device with the backend using `/api/devices`, sending a generated **InstallationId** along with device metadata.

If a device with the same `(UserId, InstallationId)` already exists, the backend will reuse the existing device record instead of creating a duplicate. Otherwise, a new device record will be created.

#### InstallationId Design

An `InstallationId` will be introduced for mobile devices to uniquely identify a specific app installation.
A **unique constraint `(UserId, InstallationId)`** will be enforced at the database level to prevent duplicate device registrations for the same user installation.

Note: If the user uninstalls and reinstalls the mobile application, the local InstallationId will be lost and a new device will be registered. This behavior is acceptable and mirrors common industry practices.

#### Device JWT Design

Device-specific JWTs will include claims such as:

* `device_id`
* `user_id`
* `token_version`

These tokens allow the backend to identify the calling device without relying on request body parameters. For example, endpoints such as `/api/timelogs` will extract the `DeviceId` directly from the Device JWT rather than trusting client-supplied identifiers.

#### API Response Design

The `LinkDesktopResponse` DTO currently returns a `DeviceJwt`.
Returning `DeviceId` alongside the token is being considered to simplify client-side implementation, although the DeviceId is already embedded within the JWT payload.

#### Device Entity Future Enhancements

Planned fields for the `Device` entity include:

* `TokenVersion` – enables device token revocation.
* `IsRevoked` – allows disabling compromised devices.
* `LastDataSyncAt` – records the last successful device synchronization.

These fields will support device revocation, security hardening, and improved synchronization tracking in future development phases.

---

## Design Update — Desktop Linking Flow Implementation

Today the backend implementation of the **desktop linking flow** was largely completed. The goal of this feature is to securely connect a desktop application to a user account using a **one-time linking token**.

### 1. Link Token Decoding Process

The desktop client sends the linking token as a **Base64URL string**. The backend performs the following steps to safely decode and validate it:

1. Convert Base64URL → Base64

   * Replace `-` with `+`
   * Replace `_` with `/`

2. Restore Base64 padding

   * If `length % 4 == 2` → append `==`
   * If `length % 4 == 3` → append `=`
   * If `length % 4 == 1` → treat token as invalid

3. Decode Base64 → `byte[]`

4. Validate decoded token length

   * Expected length: **32 bytes**

If any step fails, the API throws:

```
UnauthorizedException("Invalid linking token")
```

All invalid tokens return the same response to avoid leaking information.

---

### 2. Token Hash Validation

After decoding:

1. Compute SHA256 hash of the decoded bytes.
2. Query the database using the hash:

```
DesktopLinkTokens
WHERE TokenHash == hashBytes
```

Validation rules:

* Token must exist
* Token must not be used
* Token must not be expired

If any validation fails → return `401 Unauthorized`.

---

### 3. Device Creation After Successful Token Validation

Once the token is validated:

1. Mark the token as used:

```
tokendb.MarkAsUsed()
```

2. Create a new device record:

```
Device
{
    Id = Guid.NewGuid(),
    UserId = tokendb.UserId,
    DeviceName = command.DeviceName,
    Platform = command.Platform,
    CreatedAt = DateTime.UtcNow
}
```

3. Save changes to the database.

Important rule:
`UserId` comes from the **token record**, not from the client request.

---

### 4. Device JWT Generation

After creating the device, the backend generates a **Device JWT** which the desktop client will use for authentication.

JWT claims currently include:

```
device_id
user_id
```

Signing process:

1. Read secret key from configuration:

```
Jwt:Key
```

2. Convert key → UTF8 bytes.

3. Create `SymmetricSecurityKey`.

4. Create `SigningCredentials` using:

```
HmacSha256
```

5. Create `JwtSecurityToken` containing:

   * issuer
   * audience
   * claims
   * expiration
   * signing credentials

6. Convert token to string using `JwtSecurityTokenHandler`.

The generated token is returned to the client as:

```
LinkDesktopResponse.DeviceJwt
```

---

### 5. Security Rules Enforced

Key security decisions implemented:

* Raw linking tokens are **never stored**, only SHA256 hashes.
* Invalid tokens always return the same response (`401 Unauthorized`).
* Token validation includes:

  * existence
  * expiration
  * single-use enforcement.
* Device identity will later be extracted from **JWT claims**, not request bodies.

---

### 6. Current Implementation Status

Completed:

* Link token decoding and validation
* SHA256 token hash verification
* DesktopLinkToken database lookup
* Token single-use enforcement
* Device creation during linking
* Device JWT generation

Remaining future improvements:

* Device `TokenVersion` support
* Device revocation system
* Moving JWT generation into a dedicated service

---

*This document is a living reference. Update it as new features are implemented, decisions are made, or the architecture evolves.*