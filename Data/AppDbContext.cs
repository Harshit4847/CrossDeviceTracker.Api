using Microsoft.EntityFrameworkCore;
using CrossDeviceTracker.Api.Models.Entities;

namespace CrossDeviceTracker.Api.Data
{
    public class AppDbContext : DbContext
    {
        public AppDbContext(DbContextOptions<AppDbContext> options)
            : base(options)
        {
        }

        public DbSet<User> Users { get; set; }
        public DbSet<TimeLog> TimeLogs { get; set; }
        public DbSet<Device> Devices { get; set; }
        public DbSet<DesktopLinkToken> DesktopLinkTokens { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            // users table
            modelBuilder.Entity<User>(entity =>
            {
                entity.ToTable("users");

                entity.HasKey(u => u.Id);

                entity.HasIndex(u => u.Email)
                      .IsUnique();
                entity.Property(u => u.Email)
                .IsRequired()
                .HasMaxLength(255);

                entity.Property(u => u.PasswordHash)
                      .IsRequired();

                entity.Property(u => u.CreatedAt);
            });

            // time_logs table
            modelBuilder.Entity<TimeLog>(entity =>
            {
                entity.ToTable("time_logs");

                entity.HasKey(t => t.Id);

                entity.Property(t => t.AppName)
                      .IsRequired()
                      .HasMaxLength(255);

                entity.Property(t => t.StartTime).IsRequired();
                entity.Property(t => t.EndTime).IsRequired();
                entity.Property(t => t.DurationSeconds).IsRequired();
                entity.Property(t => t.CreatedAt);

                entity.HasOne<User>()
                      .WithMany()
                      .HasForeignKey(t => t.UserId)
                      .OnDelete(DeleteBehavior.Cascade);
            });

            // devices table
            modelBuilder.Entity<Device>(entity =>
            {
                entity.ToTable("devices");
                entity.HasKey(d => d.Id);
                entity.Property(d => d.DeviceName)
                      .IsRequired()
                      .HasMaxLength(255);
                entity.Property(d => d.Platform)
                      .IsRequired()
                      .HasMaxLength(100);
                entity.Property(d => d.CreatedAt);
                entity.HasOne<User>()
                      .WithMany()
                      .HasForeignKey(d => d.UserId)
                      .OnDelete(DeleteBehavior.Cascade);
            });

            // desktop_link_tokens table
            modelBuilder.Entity<DesktopLinkToken>(entity =>
            {
                entity.ToTable("desktop_link_tokens");

                entity.HasKey(t => t.Id);

                entity.Property(t => t.Id)
                      .HasColumnName("id");

                entity.Property(t => t.UserId)
                      .HasColumnName("user_id")
                      .IsRequired();

                entity.Property(t => t.TokenHash)
                      .HasColumnName("token_hash")
                      .IsRequired();

                entity.Property(t => t.ExpiresAt)
                      .HasColumnName("expires_at")
                      .IsRequired();

                entity.Property(t => t.CreatedAt)
                      .HasColumnName("created_at")
                      .IsRequired();

                entity.Property(t => t.IsUsed)
                      .HasColumnName("is_used")
                      .IsRequired();

                // TokenHash must be unique
                entity.HasIndex(t => t.TokenHash)
                      .IsUnique();

                // One unused token per user (Postgres partial unique index)
                entity.HasIndex(t => t.UserId)
                      .IsUnique()
                      .HasFilter("is_used = false");

                // FK to users
                entity.HasOne(t => t.User)
                      .WithMany()
                      .HasForeignKey(t => t.UserId)
                      .OnDelete(DeleteBehavior.Cascade);
            });
        }
    }
}

