from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models, transaction


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ATASAN = "ATASAN", "Atasan"

    nama = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=15, choices=Role.choices, default=Role.ADMIN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nama or self.username


class Fasilitas(models.Model):
    class Kategori(models.TextChoices):
        RUANGAN = "RUANGAN", "Ruangan"
        KELAS = "KELAS", "Kelas"
        LABORATORIUM = "LABORATORIUM", "Laboratorium"
        LABORATORIUM_SIMULATOR = "LABORATORIUM_SIMULATOR", "Laboratorium Simulator"
        LAINNYA = "LAINNYA", "Lainnya"

    class Status(models.TextChoices):
        AKTIF = "AKTIF", "Aktif"
        NONAKTIF = "NONAKTIF", "Nonaktif"

    nama_fasilitas = models.CharField(max_length=150)
    kategori = models.CharField(max_length=30, choices=Kategori.choices)
    lokasi = models.CharField(max_length=150)
    kapasitas = models.PositiveIntegerField()
    deskripsi = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AKTIF)
    keterangan_tambahan = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Fasilitas"
        ordering = ["nama_fasilitas"]

    def __str__(self):
        return self.nama_fasilitas


# Mapping kategori fasilitas ke prefix kode reservasi.
# Tambah entry baru di sini jika kategori baru ditambahkan ke Fasilitas.Kategori.
KATEGORI_PREFIX_MAP = {
    Fasilitas.Kategori.KELAS: "KLS",
    Fasilitas.Kategori.LABORATORIUM: "LAB",
    Fasilitas.Kategori.LABORATORIUM_SIMULATOR: "SIM",
    Fasilitas.Kategori.RUANGAN: "RSG",
    Fasilitas.Kategori.LAINNYA: "LNY",
}


def _generate_kode_reservasi(fasilitas):
    """
    Menghasilkan kode reservasi unik berdasarkan kategori fasilitas.
    Format: {PREFIX}{NOMOR_URUT_6_DIGIT}
    Contoh: KLS000001, LAB000003, SIM000002

    Fungsi ini harus dipanggil di dalam blok `with transaction.atomic()`
    agar aman dari duplikasi pada kondisi concurrent.
    """
    prefix = KATEGORI_PREFIX_MAP.get(fasilitas.kategori, "RSV")
    # Hitung jumlah reservasi yang sudah memiliki kode dengan prefix ini,
    # menggunakan select_for_update melalui pemanggilan di view.
    # Ambil nomor urut berikutnya dengan cara yang aman dari race condition:
    # ambil kode terakhir untuk prefix ini, parse nomornya, lalu +1.
    existing = (
        Reservasi.objects.filter(kode_reservasi__startswith=prefix)
        .order_by("-kode_reservasi")
        .values_list("kode_reservasi", flat=True)
        .first()
    )
    if existing:
        try:
            last_num = int(existing[len(prefix):])
        except (ValueError, IndexError):
            last_num = 0
        next_num = last_num + 1
    else:
        next_num = 1
    return f"{prefix}{next_num:06d}"


class Reservasi(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Menunggu Approval"
        APPROVED = "APPROVED", "Disetujui"
        REJECTED = "REJECTED", "Ditolak"
        NEEDS_REVISION = "NEEDS_REVISION", "Perlu Diperbaiki"
        CANCELLED = "CANCELLED", "Dibatalkan"

    pemohon = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reservasi")
    fasilitas = models.ForeignKey(Fasilitas, on_delete=models.PROTECT, related_name="reservasi")
    tanggal = models.DateField()
    jam_mulai = models.TimeField()
    jam_selesai = models.TimeField()
    keperluan = models.CharField(max_length=255)
    keterangan = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    alasan_penolakan = models.TextField(blank=True)
    alasan_pembatalan = models.TextField(blank=True)
    # Kode unik reservasi. Nullable untuk kompatibilitas data lama.
    # Diisi otomatis saat Admin mengajukan reservasi baru; tidak pernah diubah setelahnya.
    kode_reservasi = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-tanggal", "jam_mulai"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(jam_selesai__gt=models.F("jam_mulai")),
                name="reservasi_jam_selesai_setelah_mulai",
            ),
        ]

    def clean(self):
        if self.jam_mulai and self.jam_selesai and self.jam_selesai <= self.jam_mulai:
            raise ValidationError({"jam_selesai": "Jam selesai harus lebih besar dari jam mulai."})

    def __str__(self):
        kode = f"[{self.kode_reservasi}] " if self.kode_reservasi else ""
        return f"{kode}{self.fasilitas} - {self.tanggal}"


class Notifikasi(models.Model):
    penerima = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifikasi")
    judul = models.CharField(max_length=200)
    pesan = models.TextField()
    status_baca = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Notifikasi"
        ordering = ["-created_at"]

    def __str__(self):
        return self.judul


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    aksi = models.CharField(max_length=100)
    entitas = models.CharField(max_length=100)
    entitas_id = models.PositiveBigIntegerField(null=True, blank=True)
    detail = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.aksi} - {self.entitas}"
