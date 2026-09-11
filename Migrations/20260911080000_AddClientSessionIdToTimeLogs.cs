using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace CrossDeviceTracker.Api.Migrations
{
    public partial class AddClientSessionIdToTimeLogs : Migration
    {
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "ClientSessionId",
                table: "time_logs",
                type: "character varying(200)",
                maxLength: 200,
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "IX_time_logs_DeviceId_ClientSessionId",
                table: "time_logs",
                columns: new[] { "DeviceId", "ClientSessionId" },
                unique: true,
                filter: "\"ClientSessionId\" IS NOT NULL");
        }

        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_time_logs_DeviceId_ClientSessionId",
                table: "time_logs");

            migrationBuilder.DropColumn(
                name: "ClientSessionId",
                table: "time_logs");
        }
    }
}
