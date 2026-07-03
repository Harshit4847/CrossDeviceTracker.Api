using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CrossDeviceTracker.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddDeviceSecurityFields : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "InstallationId",
                table: "devices",
                type: "character varying(100)",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "IsRevoked",
                table: "devices",
                type: "boolean",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "LastDataSyncAt",
                table: "devices",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "TokenVersion",
                table: "devices",
                type: "integer",
                nullable: false,
                defaultValue: 0);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "InstallationId",
                table: "devices");

            migrationBuilder.DropColumn(
                name: "IsRevoked",
                table: "devices");

            migrationBuilder.DropColumn(
                name: "LastDataSyncAt",
                table: "devices");

            migrationBuilder.DropColumn(
                name: "TokenVersion",
                table: "devices");
        }
    }
}
