from django.db import migrations, models


def migrate_roles(apps, schema_editor):
    User = apps.get_model("core", "User")
    User.objects.filter(role="PEMOHON").update(role="ADMIN")
    User.objects.filter(role__in=["OPERATOR", "ADMIN"]).update(role="SUPER_ADMIN")


class Migration(migrations.Migration):
    dependencies = [("core", "0002_reservasi_pembatalan_user_roles")]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("aksi", models.CharField(max_length=100)),
                ("entitas", models.CharField(max_length=100)),
                ("entitas_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("detail", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="audit_logs", to="core.user")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.RunPython(migrate_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(choices=[("ADMIN", "Admin"), ("SUPER_ADMIN", "Super Admin"), ("ATASAN", "Atasan")], default="ADMIN", max_length=15),
        ),
    ]
