using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CrossDeviceTracker.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddClientSessionIdToTimeLogs : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "ClientSessionId",
                table: "time_logs",
                type: "character varying(36)",
                maxLength: 36,
                nullable: false);

            migrationBuilder.CreateTable(
                name: "app_aliases",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "uuid", nullable: false),
                    CanonicalName = table.Column<string>(type: "character varying(255)", maxLength: 255, nullable: false),
                    Alias = table.Column<string>(type: "character varying(255)", maxLength: 255, nullable: false),
                    Platform = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_app_aliases", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_time_logs_ClientSessionId_DeviceId",
                table: "time_logs",
                columns: new[] { "ClientSessionId", "DeviceId" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_time_logs_DeviceId",
                table: "time_logs",
                column: "DeviceId");

            migrationBuilder.CreateIndex(
                name: "IX_app_aliases_Alias_Platform",
                table: "app_aliases",
                columns: new[] { "Alias", "Platform" },
                unique: true);

            migrationBuilder.AddForeignKey(
                name: "FK_time_logs_devices_DeviceId",
                table: "time_logs",
                column: "DeviceId",
                principalTable: "devices",
                principalColumn: "Id",
                onDelete: ReferentialAction.Cascade);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_time_logs_devices_DeviceId",
                table: "time_logs");

            migrationBuilder.DropTable(
                name: "app_aliases");

            migrationBuilder.DropIndex(
                name: "IX_time_logs_ClientSessionId_DeviceId",
                table: "time_logs");

            migrationBuilder.DropIndex(
                name: "IX_time_logs_DeviceId",
                table: "time_logs");

            migrationBuilder.DropColumn(
                name: "ClientSessionId",
                table: "time_logs");
        }
    }
}
