from django.core.management.base import BaseCommand

from core.models import Fasilitas, User


class Command(BaseCommand):
    help = "Membuat akun dan fasilitas contoh SARPAS (aman dijalankan berulang)."

    def handle(self, *args, **options):
        akun = [
            ("admin", "Admin BP3IP", "admin@sarpas.local", User.Role.ADMIN),
            ("superadmin", "Super Admin BP3IP", "superadmin@sarpas.local", User.Role.SUPER_ADMIN),
            ("atasan", "Atasan BP3IP", "atasan@sarpas.local", User.Role.ATASAN),
        ]
        for username, nama, email, role in akun:
            user, dibuat = User.objects.get_or_create(
                username=username,
                defaults={"nama": nama, "email": email, "role": role},
            )
            if dibuat:
                user.set_password("Sarpas123!")
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Akun {username} dibuat."))
            else:
                self.stdout.write(f"Akun {username} sudah ada.")

        fasilitas = [
            ("Ruang Rapat A", Fasilitas.Kategori.RUANGAN, "Gedung A", 20),
            ("Kelas 101", Fasilitas.Kategori.KELAS, "Gedung B", 30),
            ("Laboratorium Simulator", Fasilitas.Kategori.LABORATORIUM_SIMULATOR, "Gedung C", 15),
        ]
        for nama, kategori, lokasi, kapasitas in fasilitas:
            _, dibuat = Fasilitas.objects.get_or_create(
                nama_fasilitas=nama,
                defaults={"kategori": kategori, "lokasi": lokasi, "kapasitas": kapasitas},
            )
            if dibuat:
                self.stdout.write(self.style.SUCCESS(f"Fasilitas {nama} dibuat."))
