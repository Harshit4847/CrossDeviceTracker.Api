# Cross Device Screen Time Tracker — Project Documentation

> **Author:** Harshit Yadav  
> **Last Updated:** July 14, 2026  
> **Version:** 1.2  
> **Repository:** [github.com/Harshit4847/CrossDeviceTracker.Api](https://github.com/Harshit4847/CrossDeviceTracker.Api)

> This document reflects the current implementation in the repository as of July 14, 2026.

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
| **Backend API** | ASP.NET Core (.NET 10.0) | JWT auth, device linking, time log storage, validation, centralized analytics aggregation |
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
│   ├── TimeLogsController.cs       # GET/POST /api/timelogs
│   ├── DashboardController.cs      # GET /api/dashboard/* endpoints
│   └── AnalyticsController.cs      # GET /api/analytics/* endpoints
│
├── Services/                       # Business logic layer
│   ├── IAuthService.cs             # Auth interface
│   ├── AuthService.cs              # Registration, login, JWT generation
│   ├── IDeviceService.cs           # Device interface
│   ├── DeviceService.cs            # Device CRUD, desktop link token, linking
│   ├── ITimeLogService.cs          # TimeLog interface
│   ├── TimeLogService.cs           # Time log creation, paginated retrieval
│   ├── IDashboardService.cs        # Dashboard interface
│   ├── DashboardService.cs         # Dashboard analytics with interval merging
│   ├── ITimeAnalyticsService.cs    # Time analytics interface
│   ├── TimeAnalyticsService.cs     # Interval merging, attention time calculation
│   ├── IAppNormalizationService.cs # App name normalization interface
│   ├── AppNormalizationService.cs  # App alias lookup for normalization
│   ├── ICurrentUserService.cs      # Current user interface
│   └── CurrentUserService.cs       # Extracts UserId from JWT claims
│
├── Models/
│   ├── Entities/                   # EF Core database entities
│   │   ├── User.cs
│   │   ├── Device.cs
│   │   ├── TimeLog.cs
│   │   ├── DesktopLinkToken.cs     # Sealed entity with domain invariants
│   │   └── AppAlias.cs             # App name normalization entity
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
│   │   ├── PairDeviceRequest.cs    # Placeholder
│   │   └── Dashboard/              # Dashboard-specific DTOs
│   │       ├── DashboardSummaryResponse.cs
│   │       ├── AppUsageResponse.cs
│   │       ├── DeviceUsageResponse.cs
│   │       ├── TimelineResponse.cs
│   │       ├── DailyUsageResponse.cs
│   │       ├── WeeklyUsageResponse.cs
│   │       ├── MonthlyUsageResponse.cs
│   │       └── HourlyUsageResponse.cs
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
│       └── TimeAnalyticsServiceTests.cs
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
│ CreatedAt│   │   │ InstallationId│       │ CreatedAt        │
└──────────┘   │   │ TokenVersion │       │ IsUsed           │
               │   │ IsRevoked    │       └──────────────────┘
               │   │ LastDataSyncAt│
               │   │ CreatedAt    │
               │   └──────────────┘
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
               │
               │   ┌──────────────┐
               └──▶│  AppAliases  │
                   │              │
                   │ Id (PK)      │
                   │ CanonicalName│
                   │ Alias        │
                   │ Platform     │
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
| `InstallationId` | `string(255)` | — | Unique identifier for device installation |
| `TokenVersion` | `int` | — | Version counter for device JWT revocation |
| `IsRevoked` | `bool` | — | Whether device access is revoked |
| `LastDataSyncAt` | `DateTime` | — | Timestamp of last data sync |
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

#### `app_aliases`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `Id` | `Guid` | PK | Generated by application |
| `CanonicalName` | `string(255)` | Required | Standardized app name |
| `Alias` | `string(255)` | Required | Alternative app name to normalize |
| `Platform` | `string(100)` | Required | Platform for the alias |
| `CreatedAt` | `DateTime` | — | UTC timestamp |

**Special Index:** `UNIQUE(alias, platform)` — Ensures each alias is unique per platform.

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

Anemic entity with device management fields.

```csharp
public class Device
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public string DeviceName { get; set; }
    public string Platform { get; set; }
    public string InstallationId { get; set; }
    public int TokenVersion { get; set; }
    public bool IsRevoked { get; set; }
    public DateTime? LastDataSyncAt { get; set; }
    public DateTime CreatedAt { get; set; }
}
```

**Fields:**
- `InstallationId` - Unique identifier for device installation
- `TokenVersion` - Version counter for device JWT revocation
- `IsRevoked` - Whether device access is revoked
- `LastDataSyncAt` - Timestamp of last data sync

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

### 8.4 AppAlias Entity

Simple anemic entity for app name normalization.

```csharp
public class AppAlias
{
    public Guid Id { get; set; }
    public string CanonicalName { get; set; }
    public string Alias { get; set; }
    public string Platform { get; set; }
    public DateTime CreatedAt { get; set; }
}
```

**Purpose:** Maps alternative app names to canonical names for normalization across platforms.

### 8.5 DesktopLinkToken Entity (Rich Domain Entity)

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

The system uses two token shapes in the current implementation:

| Token Type | Issued To | Claims | Used For |
|-----------|-----------|--------|----------|
| **User JWT** | Website / API clients | `sub`/`user_id`, `email` | User-level actions such as device registration and link-token generation |
| **Device JWT** | Desktop/device clients | `device_id`, `user_id` | Device-originated time-log submission |

The backend currently issues and validates both token shapes. User JWTs are created by `AuthService`, while device JWTs are issued by `DeviceService.LinkDesktopAsync` after a successful link-token exchange.

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

### 10.3 Token Consumption (`POST /api/devices/link`) — Implemented

**Current flow:**

1. Desktop sends the raw link token, device name, and platform.
2. Backend decodes the URL-safe Base64 token into raw bytes.
3. Computes the SHA256 hash and looks up the matching token record.
4. Validates that the token exists, is still unused, and has not expired.
5. Marks the token as used and creates a new `Device` record.
6. Generates a Device JWT containing `device_id` and `user_id` claims.
7. Returns the Device JWT plus the new device ID to the client.

The implementation currently performs these steps in a straightforward EF Core save flow; a dedicated transaction wrapper is not yet introduced.

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

**Auth:** Bearer token (User JWT) — requires authentication  
**Status:** Implemented.

**Request Body:**
```json
{
  "linkToken": "base64url-encoded-token",
  "deviceName": "My Desktop",
  "platform": "Windows"
}
```

**Success Response (200 OK):**
```json
{
  "deviceJwt": "eyJhbGci...",
  "deviceId": "guid"
}
```

**Security:**
- Requires User JWT authentication
- Validates that the link token belongs to the authenticated user
- Prevents anonymous token abuse

The endpoint validates the link token, creates the device record, marks the token as used, and returns a Device JWT for future device-authenticated requests.

---

### 11.3 Time Log Endpoints

#### `POST /api/timelogs`

**Auth:** Bearer token (Device JWT containing `device_id` and `user_id` claims)
**Request Body:**
```json
{
  "packageName": "com.example.app",
  "appName": "My App",
  "startTimeUtc": "2026-03-03T08:00:00Z",
  "endTimeUtc": "2026-03-03T09:00:00Z",
  "durationSeconds": 3600,
  "createdAtUtc": "2026-03-03T09:01:00Z"
}
```
**Success Response (200 OK):**
```json
{
  "id": "guid",
  "userId": "guid",
  "deviceId": "guid",
  "appName": "My App",
  "startTime": "2026-03-03T08:00:00Z",
  "endTime": "2026-03-03T09:00:00Z",
  "durationSeconds": 3600,
  "createdAt": "2026-03-03T09:01:00Z"
}
```

**Validation (Controller level):**
- Request body must not be null
- UserId must be valid (derived from JWT claims)
- AppName or PackageName must not be empty
- StartTimeUtc must not be in the future
- DurationSeconds must be > 0

**Validation (Service level):**
- The authenticated device must exist
- The device must belong to the authenticated user (`ForbiddenException` if not)

**Server Behavior:**
- AppName falls back to PackageName if AppName is null/empty
- Uses client-provided StartTimeUtc, EndTimeUtc, CreatedAtUtc directly
- `Id` is generated by server

---

#### `POST /api/timelogs/batch`

**Auth:** Bearer token (Device JWT containing `device_id` and `user_id` claims)
**Request Body:**
```json
[
  {
    "packageName": "com.example.app1",
    "appName": "App 1",
    "startTimeUtc": "2026-03-03T08:00:00Z",
    "endTimeUtc": "2026-03-03T08:30:00Z",
    "durationSeconds": 1800,
    "createdAtUtc": "2026-03-03T08:31:00Z"
  },
  {
    "packageName": "com.example.app2",
    "appName": "App 2",
    "startTimeUtc": "2026-03-03T08:30:00Z",
    "endTimeUtc": "2026-03-03T09:00:00Z",
    "durationSeconds": 1800,
    "createdAtUtc": "2026-03-03T09:01:00Z"
  }
]
```
**Success Response (200 OK):**
```json
[
  {
    "id": "guid",
    "userId": "guid",
    "deviceId": "guid",
    "appName": "App 1",
    "startTime": "2026-03-03T08:00:00Z",
    "endTime": "2026-03-03T08:30:00Z",
    "durationSeconds": 1800,
    "createdAt": "2026-03-03T08:31:00Z"
  },
  {
    "id": "guid",
    "userId": "guid",
    "deviceId": "guid",
    "appName": "App 2",
    "startTime": "2026-03-03T08:30:00Z",
    "endTime": "2026-03-03T09:00:00Z",
    "durationSeconds": 1800,
    "createdAt": "2026-03-03T09:01:00Z"
  }
]
```

**Validation (Controller level):**
- Request body must not be null or empty
- UserId must be valid (derived from JWT claims)

**Validation (Service level):**
- The authenticated device must exist
- The device must belong to the authenticated user (`ForbiddenException` if not)
- Each request in the batch is validated individually
- DurationSeconds must be > 0 for each entry

**Server Behavior:**
- All time logs are saved in a single database transaction
- AppName falls back to PackageName if AppName is null/empty
- Uses client-provided StartTimeUtc, EndTimeUtc, CreatedAtUtc directly

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

### 11.4 Dashboard Endpoints

#### `GET /api/dashboard/summary`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
{
  "today": {
    "totalScreenTimeSeconds": 19872,
    "totalDeviceUsageSeconds": 24120,
    "overlapTimeSeconds": 4248,
    "sessionCount": 45
  },
  "yesterday": {
    "totalScreenTimeSeconds": 21500,
    "sessionCount": 52
  },
  "thisWeek": {
    "totalScreenTimeSeconds": 145000,
    "sessionCount": 320
  },
  "thisMonth": {
    "totalScreenTimeSeconds": 580000,
    "sessionCount": 1280
  },
  "deviceCount": 3,
  "appCount": 45,
  "mostUsedApp": {
    "appName": "YouTube",
    "durationSeconds": 7200
  }
}
```

**Key Features:**
- Uses interval merging algorithm to calculate accurate cross-device screen time
- `totalScreenTimeSeconds` - Merged duration (actual attention time)
- `totalDeviceUsageSeconds` - Raw sum of all device durations
- `overlapTimeSeconds` - Time saved from double counting (raw - merged)

---

#### `GET /api/dashboard/apps`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter
- `deviceId` (optional, Guid) - Filter by specific device
- `platform` (optional, string) - Filter by platform

**Response (200 OK):**
```json
[
  {
    "appName": "YouTube",
    "durationSeconds": 7200,
    "percentage": 36.2,
    "sessionCount": 25
  },
  {
    "appName": "Chrome",
    "durationSeconds": 5400,
    "percentage": 27.1,
    "sessionCount": 18
  }
]
```

**Note:** Uses raw duration (not merged) to show per-app time accurately.

---

#### `GET /api/dashboard/devices`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
[
  {
    "deviceName": "My Desktop",
    "platform": "Windows",
    "durationSeconds": 12000,
    "percentage": 60.3,
    "sessionCount": 35
  },
  {
    "deviceName": "Pixel 8",
    "platform": "Android",
    "durationSeconds": 7876,
    "percentage": 39.7,
    "sessionCount": 28
  }
]
```

**Note:** Uses raw duration (not merged) to show per-device time accurately.

---

#### `GET /api/dashboard/timeline`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
{
  "entries": [
    {
      "start": "2026-03-03T08:00:00Z",
      "end": "2026-03-03T09:00:00Z",
      "app": "YouTube",
      "device": "My Desktop",
      "platform": "Windows",
      "durationSeconds": 3600
    }
  ]
}
```

---

### 11.5 Analytics Endpoints

#### `GET /api/analytics/daily`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
{
  "days": [
    {
      "date": "2026-03-03T00:00:00Z",
      "durationSeconds": 19872,
      "sessionCount": 45
    }
  ]
}
```

---

#### `GET /api/analytics/weekly`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
{
  "weeks": [
    {
      "weekStart": "2026-02-28T00:00:00Z",
      "weekEnd": "2026-03-06T23:59:59Z",
      "durationSeconds": 145000,
      "sessionCount": 320
    }
  ]
}
```

---

#### `GET /api/analytics/monthly`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
{
  "months": [
    {
      "year": 2026,
      "month": 3,
      "durationSeconds": 580000,
      "sessionCount": 1280
    }
  ]
}
```

---

#### `GET /api/analytics/hourly`

**Auth:** Bearer token (User JWT)  
**Query Parameters:**
- `from` (optional, DateTime) - Start date filter
- `to` (optional, DateTime) - End date filter

**Response (200 OK):**
```json
{
  "hours": [
    {
      "hour": 9,
      "durationSeconds": 7200,
      "sessionCount": 12
    }
  ]
}
```

---

### 11.6 Dashboard Design Decisions

**Backend Aggregation:** All dashboard and analytics endpoints provide pre-aggregated data computed on the backend using interval merging. This architecture:
- Reduces data transfer (clients get aggregated stats instead of raw logs)
- Improves performance (backend does the heavy aggregation once)
- Ensures consistency (single source of truth for calculations)
- Scales better with large datasets (no need to download millions of log entries)

**Interval Merging Algorithm:** 
- Merges overlapping time intervals from multiple devices to calculate accurate cross-device screen time
- Example: Desktop 10:00-11:00 + Android 10:30-11:30 = Merged 10:00-11:30 (90 min, not 120 min)
- Handles triple overlaps and complex scenarios correctly

**Raw vs Merged Data:**
- Dashboard Summary: Uses merged intervals for total screen time
- App Usage: Uses raw duration for per-app accuracy
- Device Usage: Uses raw duration for per-device accuracy
- Analytics: Uses merged intervals for time period accuracy

**When to use raw TimeLogs API:**
- Displaying detailed timeline views
- Exporting data for analysis
- Searching/filtering specific sessions
- Debugging individual sessions

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
builder.Services.AddScoped<IDashboardService, DashboardService>();
builder.Services.AddScoped<ITimeAnalyticsService, TimeAnalyticsService>();
builder.Services.AddScoped<IAppNormalizationService, AppNormalizationService>();
builder.Services.AddScoped<ICurrentUserService, CurrentUserService>();
builder.Services.AddScoped<IPasswordHasher<User>, PasswordHasher<User>>();
builder.Services.AddMemoryCache();
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
| `CreateDevice(userId, request)` | Creates a basic device entity for the authenticated user and returns the created device |
| `GetDevicesForUser(userId)` | Queries devices with `AsNoTracking()` → maps to `DeviceResponse` list |
| `GenerateDesktopLinkTokenAsync(userId)` | Generates a crypto token → hashes it → stores the hash → returns the raw token |
| `LinkDesktopAsync(command)` | Validates the token, marks it as used, creates the device, and issues a Device JWT |

### 12.5 TimeLogService

| Method | Behavior |
|--------|----------|
| `CreateTimeLog(userId, request)` | Validates device ownership → saves → returns `TimeLogResponse` |
| `CreateTimeLogsBatch(userId, requests)` | Validates each request → saves all in single transaction → returns `List<TimeLogResponse>` |
| `GetTimeLogsForUser(userId, limit, cursor)` | Cursor-based paginated query → returns `PaginatedTimeLogsResponse` |

**Design Decision:** `TimeLogService` uses two constants for pagination:
- `DefaultLimit = 20` — When no limit is specified
- `MaxLimit = 50` — Hard cap to prevent abuse

### 12.6 DashboardService

| Method | Behavior |
|--------|----------|
| `GetSummaryAsync(userId, from, to)` | Aggregates time logs with interval merging → computes today, yesterday, week, month stats with overlap metrics → returns `DashboardSummaryResponse` |
| `GetAppUsageAsync(userId, from, to, deviceId, platform)` | Groups logs by app name → calculates per-app usage with raw duration (not merged) → returns `List<AppUsageResponse>` |
| `GetDeviceUsageAsync(userId, from, to)` | Groups logs by device → calculates per-device usage with raw duration (not merged) → returns `List<DeviceUsageResponse>` |
| `GetTimelineAsync(userId, from, to)` | Returns chronological list of sessions with app, device, platform info → returns `TimelineResponse` |
| `GetDailyUsageAsync(userId, from, to)` | Groups logs by date → applies interval merging per day → returns `DailyUsageResponse` |
| `GetWeeklyUsageAsync(userId, from, to)` | Groups logs by week → applies interval merging per week → returns `WeeklyUsageResponse` |
| `GetMonthlyUsageAsync(userId, from, to)` | Groups logs by month → applies interval merging per month → returns `MonthlyUsageResponse` |
| `GetHourlyUsageAsync(userId, from, to)` | Groups logs by hour (0-23) → applies interval merging per hour → returns `HourlyUsageResponse` |

**Design Decision:** `DashboardService` uses `ITimeAnalyticsService` for interval merging calculations. The service:
- Calculates time-based aggregates with interval merging for accurate cross-device screen time
- Uses raw duration for per-app and per-device breakdowns (to show actual time spent on each)
- Applies interval merging for time period analytics (daily/weekly/monthly/hourly)
- Includes overlap metrics in summary (totalDeviceUsage, overlapTime)
- Uses MemoryCache for performance (10-second cache on summary endpoint)

### 12.7 TimeAnalyticsService

A dedicated analytics engine for time interval calculations. Designed to be reusable across services and extensible for future analytics features.

| Method | Behavior |
|--------|----------|
| `MergeIntervals(intervals)` | Sorts intervals by start time → merges overlapping intervals → returns merged non-overlapping intervals |
| `CalculateAttentionTime(intervals)` | Merges intervals → sums merged durations → returns total attention time in seconds |

**Algorithm:**
1. Sort intervals by start time
2. Iterate through sorted intervals
3. If next interval overlaps with current (next.Start <= current.End), merge by extending current.End
4. If no overlap, add current to result and start new current
5. Add final current to result

**Example:**
- Input: [10:00-11:00, 10:30-11:30, 10:20-10:40]
- Output: [10:00-11:30] (90 min, not 110 min)

**Future Expansion:**
- `CalculateOverlapTime()` - Calculate total overlap duration
- `CalculatePeakConcurrentDevices()` - Find maximum concurrent device usage
- `SplitByHour()` - Split intervals by hour buckets
- `SplitByDay()` - Split intervals by day buckets
- `SplitByWeek()` - Split intervals by week buckets
- `SplitByMonth()` - Split intervals by month buckets

### 12.8 AppNormalizationService

| Method | Behavior |
|--------|----------|
| `NormalizeAppNameAsync(appName, platform)` | Looks up app name in AppAliases table by (Alias, Platform) → returns CanonicalName if found, otherwise returns original appName |

**Purpose:** Normalizes app names across platforms for consistent analytics. For example, "com.android.chrome" and "Google Chrome" can both map to "Chrome".

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

The project has a test project at `CrossDeviceTracker.Api.Tests/` with unit tests for `TimeAnalyticsService`:

| Test | Validates |
|------|----------|
| `MergeIntervals_TripleOverlap_ShouldMergeCorrectly` | 3 devices overlapping correctly merge to single interval |
| `MergeIntervals_DoubleOverlap_ShouldMergeCorrectly` | 2 devices overlapping correctly merge |
| `MergeIntervals_NonOverlapping_ShouldNotMerge` | Non-overlapping intervals remain separate |
| `MergeIntervals_EmptyList_ShouldReturnEmpty` | Empty list handling |
| `MergeIntervals_SingleInterval_ShouldReturnSame` | Single interval identity |
| `MergeIntervals_PartialOverlap_ShouldMergeCorrectly` | Partial overlap merging |
| `MergeIntervals_MultipleOverlaps_ShouldMergeAll` | Chain of overlapping intervals |
| `CalculateAttentionTime_TripleOverlap_ShouldReturnCorrectDuration` | Attention time calculation with merging |

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
| `DashboardService` | All dashboard endpoints with various date filters |
| `AppNormalizationService` | App name lookup, fallback to original |
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
4. `20260714000000_AddAppAliases` — App aliases table for app name normalization

---

## 21. Current Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| User registration | Done | Email + password, duplicate check |
| User login + JWT | Done | HMAC-SHA256, configurable expiry |
| Device creation | Done | Basic device registration via POST /api/devices |
| List user devices | Done | GET /api/devices |
| Desktop link token generation | Done | Crypto-secure, SHA256 hashed |
| Desktop link token consumption | Done | Validates token, creates device, returns Device JWT |
| Time log creation | Done | Server-computed EndTime, device ownership validation |
| Time log retrieval (paginated) | Done | Cursor-based pagination |
| Batch time log sync | Done | POST /api/timelogs/batch endpoint |
| Device JWT issuance | Done | Implemented in the desktop link flow |
| Device fields (InstallationId, TokenVersion, IsRevoked, LastDataSyncAt) | Done | Added to Device entity |
| App aliases table | Done | AppAlias entity for app name normalization |
| Dashboard endpoints | Done | Summary, apps, devices, timeline with date filters |
| Analytics endpoints | Done | Daily, weekly, monthly, hourly analytics |
| Interval merging algorithm | Done | TimeAnalyticsService with MergeIntervals and CalculateAttentionTime |
| Overlap metrics | Done | totalDeviceUsage and overlapTime in summary |
| App normalization service | Done | AppNormalizationService for alias lookup |
| Memory caching | Done | 10-second cache on dashboard summary |
| Device revocation logic | **Not started** | No device-revocation endpoint yet |
| Exception handling middleware | Done | 401, 403, 500 mapping |
| CORS | Done (dev mode) | AllowAll — needs restriction for production |
| Swagger documentation | Done | Available in all environments |
| Unit tests | Partial | TimeAnalyticsService coverage exists; broader service/controller tests are still missing |

---

## 22. Known Issues & Incomplete Work

### 22.1 Current Gaps

1. **Device revocation endpoint is not implemented:**
   - Device entity has `IsRevoked` and `TokenVersion` fields, but there is no revoke/logout flow or dedicated device-status endpoint.

2. **Connection string logging remains in startup code:**
   - `Program.cs` still prints the configured connection string value, which is a security concern for production.

3. **CORS is permissive in development:**
   - The current `AllowAll` policy is fine for local testing, but should be restricted for production deployments.

4. **App normalization not yet integrated:**
   - `AppNormalizationService` exists but is not yet used in dashboard analytics endpoints.

### 22.2 Missing Features vs DESIGN.md

| Designed Feature | Gap |
|-----------------|-----|
| `Device.IsRevoked` field | **Done** - Added to entity |
| `Device.TokenVersion` field | **Done** - Added to entity |
| `Device.LastDataSyncAt` field | **Done** - Added to entity |
| Device JWT validation middleware | Not implemented; claim validation currently lives in services |
| Token revocation (increment TokenVersion) | Not implemented (endpoint missing) |
| Constant-time hash comparison for tokens | Not implemented (current code uses a direct EF query by hash) |
| Batch time log submission | **Done** - POST /api/timelogs/batch endpoint implemented |
| Duration tolerance validation | Not implemented |
| Time drift validation | Not implemented |
| Extreme duration check | Not implemented |
| Dashboard analytics with interval merging | **Done** - TimeAnalyticsService implemented |
| App name normalization | **Done** - AppNormalizationService and AppAlias entity implemented |

### 22.3 Naming Inconsistencies

- `desktop_link_tokens` uses snake_case column names; other tables use PascalCase
- `DeviceService._context` is declared `public readonly` instead of `private readonly`

---

## 23. Future Roadmap

### Phase 1: Complete Desktop Linking
- [x] Implement `LinkDesktopAsync` in `DeviceService`
- [x] Add `IsRevoked`, `TokenVersion`, `LastDataSyncAt` to `Device` entity
- [x] Create EF Core migration for new Device fields
- [x] Issue Device JWT on successful desktop link
- [ ] Add constant-time hash comparison for token validation

### Phase 2: Device Authentication & Revocation
- [ ] Create Device JWT validation middleware
- [ ] Implement device revocation endpoint
- [ ] Implement "logout from all devices" (TokenVersion increment)
- [ ] Add device status check endpoint (for desktop app startup)

### Phase 3: Batch Sync
- [x] Add batch time log creation endpoint (`POST /api/timelogs/batch`)
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
| 16 | Jul 14, 2026 | Interval merging for cross-device screen time | Sum raw durations, client-side merging | Merging overlapping intervals on backend provides accurate cross-device attention time without double-counting; dedicated TimeAnalyticsService for reusability |
| 17 | Jul 14, 2026 | Separate TimeAnalyticsService from DashboardService | Keep merge logic in DashboardService | Dedicated service allows reuse across multiple services, easier unit testing, and future expansion (overlap calculation, peak concurrent devices, time splitting) |
| 18 | Jul 14, 2026 | Raw duration for per-app/per-device, merged for total | Use merged for all calculations | Per-app and per-device breakdowns should show actual time spent (raw), while total screen time should account for overlaps (merged) - different metrics for different use cases |

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