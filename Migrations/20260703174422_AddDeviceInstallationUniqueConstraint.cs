using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CrossDeviceTracker.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddDeviceInstallationUniqueConstraint : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_devices_UserId",
                table: "devices");

            migrationBuilder.CreateIndex(
                name: "IX_devices_UserId_InstallationId",
                table: "devices",
                columns: new[] { "UserId", "InstallationId" },
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_devices_UserId_InstallationId",
                table: "devices");

            migrationBuilder.CreateIndex(
                name: "IX_devices_UserId",
                table: "devices",
                column: "UserId");
        }
    }
}
