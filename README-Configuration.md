# Configuration Setup Guide

## For Local Development

1. Copy `appsettings.Development.json.template` to `appsettings.Development.json`
2. Update the following values in `appsettings.Development.json`:
   - `ConnectionStrings:DefaultConnection`: Your local PostgreSQL connection string
   - `Jwt:Key`: A secure secret key (minimum 32 characters)
   - `Jwt:Issuer`: Your API issuer name
   - `Jwt:Audience`: Your client audience name

## For Production Hosting

### Option 1: Using Environment Variables (Recommended)
Set the following environment variables in your hosting provider:

```
ConnectionStrings__DefaultConnection=your-production-connection-string
Jwt__Key=your-production-jwt-key
Jwt__Issuer=your-production-issuer
Jwt__Audience=your-production-audience
```

### Option 2: Using appsettings.Production.json
1. Copy `appsettings.Production.json.template` to `appsettings.Production.json`
2. Fill in the production values
3. Deploy this file securely (never commit to Git)

## Security Notes

- Never commit `appsettings.Development.json` or `appsettings.Production.json` to Git
- Use strong, randomly generated secrets for JWT keys
- Store production secrets in your hosting provider's secret management system
- Regularly rotate your secrets and passwords
