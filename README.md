# CrossDeviceTracker.Api

A modern ASP.NET Core Web API for tracking user activities and sessions across multiple devices. Built with .NET 10.0 and Entity Framework Core with PostgreSQL.

## 🚀 Features

- **Cross-Device Tracking**: Monitor user sessions across multiple devices
- **RESTful API**: Clean and intuitive API endpoints
- **Entity Framework Core**: Database-first approach with PostgreSQL
- **Swagger/OpenAPI**: Built-in API documentation and testing interface
- **Modern Architecture**: Clean separation of concerns with Controllers, Models, Services, and Data layers

## 🛠️ Technology Stack

- **Framework**: .NET 10.0
- **Database**: PostgreSQL with Npgsql.EntityFrameworkCore.PostgreSQL 10.0.0
- **ORM**: Entity Framework Core 10.0.1
- **API Documentation**: Swashbuckle.AspNetCore 10.1.0
- **API Specification**: Microsoft.AspNetCore.OpenAPI 10.0.1

## 📁 Project Structure

```
CrossDeviceTracker.Api/
├── Controllers/          # API Controllers
│   └── AuthController.cs
├── Models/              # Data models
│   ├── DTOs/           # Data Transfer Objects
│   └── Entities/       # Database entities
├── Data/               # Database context and migrations
│   └── AppDbContext.cs
├── Services/           # Business logic layer
├── Properties/         # Project properties
├── Program.cs          # Application entry point
└── appsettings.json    # Configuration
```

## 🔧 Prerequisites

- [.NET 10.0 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)
- [PostgreSQL](https://www.postgresql.org/download/) (version 12 or higher recommended)
- IDE: Visual Studio 2025, Visual Studio Code, or JetBrains Rider

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Harshit4847/CrossDeviceTracker.Api.git
   cd CrossDeviceTracker.Api
   ```

2. **Configure the database connection**
   
   Update the connection string in `appsettings.json` or `appsettings.Development.json`:
   ```json
   {
     "ConnectionStrings": {
       "DefaultConnection": "Host=localhost;Database=crossdevicetracker;Username=your_username;Password=your_password"
     }
   }
   ```

3. **Restore NuGet packages**
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

The API will be available at:
- HTTPS: `https://localhost:7xxx`
- HTTP: `http://localhost:5xxx`

(Port numbers will be displayed in the console when the application starts)

## 📚 API Documentation

Once the application is running, access the Swagger UI documentation at:

```
https://localhost:7xxx/swagger
```

This interactive interface allows you to:
- View all available endpoints
- Test API calls directly from the browser
- See request/response schemas
- Review API authentication requirements

## 🔒 Authentication

The API includes an `AuthController` for handling authentication. Details will be added as the authentication implementation progresses.

## 🗄️ Database

The project uses Entity Framework Core with PostgreSQL. The `AppDbContext` class manages the database context and entity configurations.

### Migrations

Create a new migration:
```bash
dotnet ef migrations add MigrationName
```

Update the database:
```bash
dotnet ef database update
```

Revert the last migration:
```bash
dotnet ef database update PreviousMigrationName
```

## 🚦 Development

### Running in Development Mode

The application is configured to run Swagger in all environments. Development-specific settings can be found in `appsettings.Development.json`.

### Debug Mode

Using Visual Studio:
- Press F5 to start debugging

Using VS Code:
- Use the configured launch settings
- Or run: `dotnet run --launch-profile https`

## 🧪 Testing

(Coming soon - Unit tests and integration tests will be added)

## 📝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is currently unlicensed. Please contact the repository owner for usage rights.

## 👤 Author

**Harshit Yadav**
- GitHub: [@Harshit4847](https://github.com/Harshit4847)
- Email: official.harshit@outlook.com

## 🤝 Support

For support, please open an issue in the GitHub repository.

## 📅 Changelog

### [Unreleased]
- Initial project setup with basic structure
- Added Entity Framework Core with PostgreSQL support
- Integrated Swagger/OpenAPI documentation
- Set up AuthController foundation
- Configured DbContext and project architecture

---

⭐ If you find this project useful, please consider giving it a star on GitHub!