# Generated manually to keep the deployment migration explicit.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("PEMOHON", "Pemohon"), ("OPERATOR", "Operator SARPAS"), ("ATASAN", "Atasan"), ("ADMIN", "Admin (legacy)")],
                default="PEMOHON",
                max_length=10,
            ),
        ),
        migrations.AddField(model_name="reservasi", name="alasan_pembatalan", field=models.TextField(blank=True)),
        migrations.AddConstraint(
            model_name="reservasi",
            constraint=models.CheckConstraint(condition=models.Q(jam_selesai__gt=models.F("jam_mulai")), name="reservasi_jam_selesai_setelah_mulai"),
        ),
    ]
