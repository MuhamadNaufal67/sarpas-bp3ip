from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from .forms import ReservasiForm, fasilitas_tersedia
from .models import Fasilitas, Notifikasi, Reservasi, User
from .schedule import get_week_start, get_weekly_schedule


class SarpasTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin1", password="password-kuat-123", nama="Admin Satu",
            email="admin1@example.com", role=User.Role.ADMIN,
        )
        self.atasan = User.objects.create_user(
            username="atasan1", password="password-kuat-123", nama="Atasan Satu",
            email="atasan1@example.com", role=User.Role.ATASAN,
        )
        self.fasilitas = Fasilitas.objects.create(
            nama_fasilitas="Ruang Rapat A", kategori=Fasilitas.Kategori.RUANGAN,
            lokasi="Gedung A", kapasitas=20,
        )

    def buat_reservasi(self, status=Reservasi.Status.PENDING, mulai=time(9), selesai=time(12)):
        return Reservasi.objects.create(
            pemohon=self.admin_user, fasilitas=self.fasilitas, tanggal=date(2026, 9, 10),
            jam_mulai=mulai, jam_selesai=selesai, keperluan="Rapat", status=status,
        )

    def test_login_dan_akses_role(self):
        response = self.client.post(reverse("login"), {"username": "admin1", "password": "password-kuat-123"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        response = self.client.get(reverse("pengajuan_list"))
        self.assertRedirects(response, reverse("dashboard"))
        self.client.logout()
        self.client.login(username="atasan1", password="password-kuat-123")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_validasi_jam_dan_jadwal_bentrok(self):
        form = ReservasiForm(data={
            "fasilitas": self.fasilitas.pk, "tanggal": "2026-09-10",
            "jam_mulai": "12:00", "jam_selesai": "09:00", "keperluan": "Rapat",
        })
        self.assertFalse(form.is_valid())
        self.buat_reservasi(status=Reservasi.Status.APPROVED)
        self.assertFalse(fasilitas_tersedia(self.fasilitas, date(2026, 9, 10), time(11), time(13)))
        self.assertTrue(fasilitas_tersedia(self.fasilitas, date(2026, 9, 10), time(12), time(14)))

    def test_approval_menandai_konflik_dan_mengirim_notifikasi(self):
        pertama = self.buat_reservasi()
        kedua = self.buat_reservasi(mulai=time(10), selesai=time(13))
        admin_kedua = User.objects.create_user(
            username="admin2", password="password-kuat-123", nama="Admin Dua",
            email="admin2@example.com", role=User.Role.ADMIN,
        )
        kedua.pemohon = admin_kedua
        kedua.save(update_fields=["pemohon"])
        self.client.login(username="atasan1", password="password-kuat-123")
        response = self.client.post(reverse("pengajuan_approve", args=[pertama.pk]))
        self.assertRedirects(response, reverse("pengajuan_detail", args=[pertama.pk]))
        pertama.refresh_from_db()
        kedua.refresh_from_db()
        self.assertEqual(pertama.status, Reservasi.Status.APPROVED)
        self.assertEqual(kedua.status, Reservasi.Status.NEEDS_REVISION)
        self.assertEqual(Notifikasi.objects.filter(penerima=self.admin_user).count(), 1)
        self.assertEqual(Notifikasi.objects.filter(penerima=admin_kedua).count(), 1)

    def test_penolakan_menyimpan_alasan(self):
        reservasi = self.buat_reservasi()
        self.client.login(username="atasan1", password="password-kuat-123")
        self.client.post(reverse("pengajuan_reject", args=[reservasi.pk]), {"alasan_penolakan": "Ruangan digunakan kegiatan lain."})
        reservasi.refresh_from_db()
        self.assertEqual(reservasi.status, Reservasi.Status.REJECTED)
        self.assertEqual(reservasi.alasan_penolakan, "Ruangan digunakan kegiatan lain.")

    def test_jadwal_mingguan_hanya_memuat_reservasi_disetujui(self):
        approved = self.buat_reservasi(status=Reservasi.Status.APPROVED)
        self.buat_reservasi(status=Reservasi.Status.DRAFT, mulai=time(13), selesai=time(14))
        self.buat_reservasi(status=Reservasi.Status.PENDING, mulai=time(14), selesai=time(15))
        schedule = get_weekly_schedule(get_week_start("2026-09-10"))
        bookings = [booking for row in schedule["rows"] for cell in row["cells"] for booking in cell["bookings"]]
        self.assertIn(approved, bookings)
        self.assertEqual({booking.status for booking in bookings}, {Reservasi.Status.APPROVED})
        self.assertTrue(any(not cell["bookings"] for row in schedule["rows"] for cell in row["cells"]))

    def test_notifikasi_user_badge_dan_tandai_dibaca(self):
        own = Notifikasi.objects.create(penerima=self.admin_user, judul="Untuk Admin", pesan="Pesan admin")
        Notifikasi.objects.create(penerima=self.atasan, judul="Untuk Atasan", pesan="Pesan atasan")
        self.client.login(username="admin1", password="password-kuat-123")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'class="header-badge">1')
        self.assertContains(response, "Untuk Admin")
        self.assertNotContains(response, "Untuk Atasan")
        self.client.post(reverse("notifikasi_baca", args=[own.pk]))
        own.refresh_from_db()
        self.assertTrue(own.status_baca)

    def test_dashboard_admin_dan_atasan_memuat_jadwal(self):
        self.buat_reservasi(status=Reservasi.Status.APPROVED)
        self.client.login(username="admin1", password="password-kuat-123")
        response = self.client.get(reverse("dashboard"), {"minggu": "2026-09-10"})
        self.assertContains(response, "Jadwal Reservasi Mingguan")
        self.assertContains(response, "Ruang Rapat A")
        self.client.logout()
        self.client.login(username="atasan1", password="password-kuat-123")
        self.assertEqual(self.client.get(reverse("dashboard"), {"minggu": "2026-09-10"}).status_code, 200)

    def test_jadwal_mengabaikan_semua_status_non_final_dan_minggu_lain(self):
        approved = self.buat_reservasi(status=Reservasi.Status.APPROVED)
        for status in [
            Reservasi.Status.DRAFT, Reservasi.Status.PENDING, Reservasi.Status.REJECTED,
            Reservasi.Status.NEEDS_REVISION, Reservasi.Status.CANCELLED,
        ]:
            self.buat_reservasi(status=status)
        Reservasi.objects.create(
            pemohon=self.admin_user, fasilitas=self.fasilitas, tanggal=date(2026, 9, 17),
            jam_mulai=time(9), jam_selesai=time(11), keperluan="Minggu lain",
            status=Reservasi.Status.APPROVED,
        )
        schedule = get_weekly_schedule(get_week_start("2026-09-10"))
        visible = [booking for row in schedule["rows"] for cell in row["cells"] for booking in cell["bookings"]]
        self.assertEqual(visible, [approved])
