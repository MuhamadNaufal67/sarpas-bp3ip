from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Menambahkan field kode_reservasi ke model Reservasi.
    Field dibuat nullable agar kompatibel dengan data reservasi yang sudah ada.
    Reservasi lama tidak akan mendapat kode otomatis; mereka tetap dapat dibaca
    dan ditampilkan dengan kode '-' di template.
    """
    dependencies = [("core", "0003_auditlog_redefine_roles")]

    operations = [
        migrations.AddField(
            model_name="reservasi",
            name="kode_reservasi",
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                unique=True,
                verbose_name="Kode Reservasi",
            ),
        ),
    ]
