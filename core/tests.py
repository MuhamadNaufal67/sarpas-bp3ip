from datetime import date, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
        self.assertContains(response, "Notifikasi (1)")
        self.assertContains(response, "Untuk Admin")
        self.assertNotContains(response, "Untuk Atasan")
        self.client.post(reverse("notifikasi_baca", args=[own.pk]))
        own.refresh_from_db()
        self.assertTrue(own.status_baca)

    def test_tandai_semua_notifikasi_dibaca_hanya_milik_pengguna(self):
        milik_admin = Notifikasi.objects.create(penerima=self.admin_user, judul="Untuk Admin", pesan="Pesan admin")
        milik_atasan = Notifikasi.objects.create(penerima=self.atasan, judul="Untuk Atasan", pesan="Pesan atasan")
        self.client.login(username="admin1", password="password-kuat-123")

        response = self.client.post(reverse("notifikasi_tandai_semua_dibaca"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"marked_count": 1})
        milik_admin.refresh_from_db()
        milik_atasan.refresh_from_db()
        self.assertTrue(milik_admin.status_baca)
        self.assertFalse(milik_atasan.status_baca)

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

    def test_super_admin_kelola_akun_admin_dan_buat_admin(self):
        super_admin = User.objects.create_user(
            username="superadmin", password="password-super-123", nama="Super Admin BP3IP",
            email="superadmin@example.com", role=User.Role.SUPER_ADMIN,
        )
        self.client.login(username="superadmin", password="password-super-123")
        
        # Test halaman daftar admin
        response = self.client.get(reverse("admin_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kelola Akun Admin")
        self.assertContains(response, "admin1")

        # Test halaman form tambah admin
        response = self.client.get(reverse("admin_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tambah Akun Admin")

        # Test buat akun admin baru berhasil
        data_admin_baru = {
            "username": "admin2",
            "nama": "Admin Dua",
            "email": "admin2@bp3ip.go.id",
            "password1": "PasswordKuat#123",
            "password2": "PasswordKuat#123",
        }
        res_post = self.client.post(reverse("admin_create"), data_admin_baru)
        self.assertRedirects(res_post, reverse("admin_list"))
        
        # Pastikan user baru tersimpan dengan role ADMIN
        user_baru = User.objects.get(username="admin2")
        self.assertEqual(user_baru.role, User.Role.ADMIN)
        self.assertEqual(user_baru.nama, "Admin Dua")
        self.assertTrue(user_baru.check_password("PasswordKuat#123"))

    def test_non_super_admin_tidak_bisa_akses_kelola_akun(self):
        # Admin biasa tidak boleh akses
        self.client.login(username="admin1", password="password-kuat-123")
        res_admin = self.client.get(reverse("admin_list"))
        self.assertRedirects(res_admin, reverse("dashboard"))
        res_create = self.client.get(reverse("admin_create"))
        self.assertRedirects(res_create, reverse("dashboard"))

    def test_reservasi_create_memuat_fasilitas_json_dan_kategori(self):
        # Buat fasilitas dengan kategori KELAS, LAB, dan LAINNYA
        Fasilitas.objects.create(
            nama_fasilitas="Kelas 101", kategori=Fasilitas.Kategori.KELAS,
            lokasi="Lantai 1", kapasitas=30,
        )
        Fasilitas.objects.create(
            nama_fasilitas="Lab Simulator Navigasi", kategori=Fasilitas.Kategori.LABORATORIUM_SIMULATOR,
            lokasi="Lantai 2", kapasitas=15,
        )
        self.client.login(username="admin1", password="password-kuat-123")
        response = self.client.get(reverse("reservasi_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kategori Fasilitas")
        self.assertContains(response, "Kelas 101")
        self.assertContains(response, "Lab Simulator Navigasi")
        self.assertIn("fasilitas_json", response.context)

    def test_sidebar_hanya_menandai_ajukan_reservasi_saat_membuka_form(self):
        self.client.login(username="admin1", password="password-kuat-123")
        response = self.client.get(reverse("reservasi_create"))

        self.assertContains(
            response,
            f'href="{reverse("reservasi_create")}" class="nav-link active"',
        )
        self.assertContains(
            response,
            f'href="{reverse("reservasi_list")}" class="nav-link"',
        )
        self.assertNotContains(
            response,
            f'href="{reverse("reservasi_list")}" class="nav-link active"',
        )

    def test_tombol_sidebar_mobile_memuat_logo_bp3ip(self):
        self.client.login(username="admin1", password="password-kuat-123")
        response = self.client.get(reverse("reservasi_create"))

        self.assertContains(response, 'id="mobile-menu-toggle"')
        self.assertContains(response, 'class="mobile-menu-logo"')
        self.assertContains(response, 'src="/static/images/LOGO_BP3IP.png"')

    def test_search_dan_pagination_tabel_tabel(self):
        super_admin = User.objects.create_user(
            username="superadmin", password="password-super-123", nama="Super Admin BP3IP",
            email="superadmin@example.com", role=User.Role.SUPER_ADMIN,
        )
        self.client.login(username="superadmin", password="password-super-123")

        # 1. Search Fasilitas
        res_fas = self.client.get(reverse("fasilitas_list"), {"q": "Rapat"})
        self.assertEqual(res_fas.status_code, 200)
        self.assertContains(res_fas, "Ruang Rapat A")
        self.assertContains(res_fas, "Menampilkan hasil pencarian")

        # 2. Search Kelola Akun Admin
        res_adm = self.client.get(reverse("admin_list"), {"q": "admin1"})
        self.assertEqual(res_adm.status_code, 200)
        self.assertContains(res_adm, "admin1")

        # 3. Search Kelola Semua Reservasi
        self.buat_reservasi(status=Reservasi.Status.PENDING)
        res_man = self.client.get(reverse("reservasi_manage"), {"q": "Rapat"})
        self.assertEqual(res_man.status_code, 200)
        self.assertContains(res_man, "Ruang Rapat A")

        # 4. Search & Filter Tanggal Audit Log
        from core.models import AuditLog
        today_str = timezone.localdate().strftime("%Y-%m-%d")
        AuditLog.objects.create(actor=super_admin, aksi="UJI_LOG", entitas="Test", detail="Pencarian log berhasil")
        res_aud = self.client.get(reverse("audit_log_list"), {"q": "UJI_LOG", "tanggal": today_str})
        self.assertEqual(res_aud.status_code, 200)
        self.assertContains(res_aud, "Pencarian log berhasil")
        self.assertContains(res_aud, today_str)

    def test_super_admin_bisa_ajukan_dan_lihat_reservasi(self):
        super_admin = User.objects.create_user(
            username="superadmin_res", password="password-super-123", nama="Super Admin BP3IP",
            email="superadmin_res@example.com", role=User.Role.SUPER_ADMIN,
        )
        self.client.login(username="superadmin_res", password="password-super-123")
        
        # Super admin dapat membuka form ajukan reservasi
        response = self.client.get(reverse("reservasi_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ajukan Reservasi")

        target_date = timezone.localdate() + timedelta(days=1)
        if target_date.weekday() == 6:
            target_date += timedelta(days=1)

        # Super admin dapat submit reservasi
        post_data = {
            "fasilitas": self.fasilitas.pk,
            "tanggal": target_date.strftime("%Y-%m-%d"),
            "jam_mulai": "08:00",
            "jam_selesai": "11:00",
            "keperluan": "Rapat Koordinasi Super Admin",
        }
        res_post = self.client.post(reverse("reservasi_create"), post_data)
        self.assertRedirects(res_post, reverse("reservasi_list"))

        # Reservasi tersimpan di DB dengan pemohon super_admin
        res_obj = Reservasi.objects.filter(pemohon=super_admin).first()
        self.assertIsNotNone(res_obj)
        self.assertEqual(res_obj.keperluan, "Rapat Koordinasi Super Admin")

        # Super admin dapat melihat daftar Reservasi Saya
        res_list = self.client.get(reverse("reservasi_list"))
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, "Rapat Koordinasi Super Admin")

    def test_notifikasi_baca_semua(self):
        Notifikasi.objects.create(penerima=self.admin_user, judul="Notif 1", pesan="Pesan 1")
        Notifikasi.objects.create(penerima=self.admin_user, judul="Notif 2", pesan="Pesan 2")
        Notifikasi.objects.create(penerima=self.admin_user, judul="Notif 3", pesan="Pesan 3")
        
        self.assertEqual(self.admin_user.notifikasi.filter(status_baca=False).count(), 3)
        self.client.login(username="admin1", password="password-kuat-123")
        
        res = self.client.post(reverse("notifikasi_baca_semua"), {"next": reverse("dashboard")})
        self.assertRedirects(res, reverse("dashboard"))
        self.assertEqual(self.admin_user.notifikasi.filter(status_baca=False).count(), 0)

    def test_post_reservasi_create_view_dan_kode_reservasi(self):
        self.client.login(username="admin1", password="password-kuat-123")
        target_date = timezone.localdate() + timedelta(days=2)
        if target_date.weekday() == 6:
            target_date += timedelta(days=1)

        post_data = {
            "fasilitas": self.fasilitas.pk,
            "tanggal": target_date.strftime("%Y-%m-%d"),
            "jam_mulai": "08:00",
            "jam_selesai": "10:00",
            "keperluan": "Kuliah Umum Maritim",
            "keterangan": "Perlu proyektor",
        }
        response = self.client.post(reverse("reservasi_create"), post_data)
        self.assertRedirects(response, reverse("reservasi_list"))

        reservasi = Reservasi.objects.filter(pemohon=self.admin_user, keperluan="Kuliah Umum Maritim").first()
        self.assertIsNotNone(reservasi)
        self.assertEqual(reservasi.status, Reservasi.Status.PENDING)
        self.assertTrue(reservasi.kode_reservasi.startswith("RSG"))

    def test_reservasi_form_multiple_errors_display(self):
        self.client.login(username="admin1", password="password-kuat-123")
        # Submit form with past date and jam_selesai <= jam_mulai
        post_data = {
            "fasilitas": self.fasilitas.pk,
            "tanggal": "2020-01-01",
            "jam_mulai": "14:00",
            "jam_selesai": "10:00",
            "keperluan": "Test Error",
        }
        response = self.client.post(reverse("reservasi_create"), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "tanggal", "Reservasi tidak dapat dibuat untuk tanggal yang sudah lewat.")
        self.assertFormError(response.context["form"], "jam_selesai", "Jam selesai harus lebih besar dari jam mulai.")

    def test_fasilitas_duplicate_name_prevention_and_delete_protection(self):
        super_admin = User.objects.create_user(
            username="superadmin_fas", password="password-super-123", nama="Super Admin Fasilitas",
            email="superfas@example.com", role=User.Role.SUPER_ADMIN,
        )
        self.client.login(username="superadmin_fas", password="password-super-123")

        # Coba buat fasilitas dengan nama yang sama persis (case-insensitive)
        post_data = {
            "nama_fasilitas": "ruang rapat a",
            "kategori": Fasilitas.Kategori.RUANGAN,
            "lokasi": "Gedung Lain",
            "kapasitas": 10,
            "status": Fasilitas.Status.AKTIF,
        }
        response = self.client.post(reverse("fasilitas_create"), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "nama_fasilitas", "Nama fasilitas sudah terdaftar. Gunakan nama yang berbeda.")

        # Coba hapus fasilitas yang sudah terikat pada reservasi
        self.buat_reservasi()
        del_resp = self.client.post(reverse("fasilitas_delete", args=[self.fasilitas.pk]))
        self.assertRedirects(del_resp, reverse("fasilitas_list"))
        self.assertTrue(Fasilitas.objects.filter(pk=self.fasilitas.pk).exists())

    def test_cancel_approved_reservasi_notifies_needs_revision(self):
        super_admin = User.objects.create_user(
            username="superadmin_ccl", password="password-super-123", nama="Super Admin Cancel",
            email="superccl@example.com", role=User.Role.SUPER_ADMIN,
        )
        target_date = timezone.localdate() + timedelta(days=3)
        if target_date.weekday() == 6:
            target_date += timedelta(days=1)

        # Buat 1 reservasi APPROVED dan 1 reservasi yang tadinya konflik (NEEDS_REVISION)
        appr_res = Reservasi.objects.create(
            pemohon=self.admin_user, fasilitas=self.fasilitas, tanggal=target_date,
            jam_mulai=time(8), jam_selesai=time(11), keperluan="Event A", status=Reservasi.Status.APPROVED,
        )
        admin2 = User.objects.create_user(
            username="admin_rev", password="password-kuat-123", nama="Admin Revisi",
            email="adminrev@example.com", role=User.Role.ADMIN,
        )
        rev_res = Reservasi.objects.create(
            pemohon=admin2, fasilitas=self.fasilitas, tanggal=target_date,
            jam_mulai=time(9), jam_selesai=time(10), keperluan="Event B", status=Reservasi.Status.NEEDS_REVISION,
        )

        self.client.login(username="superadmin_ccl", password="password-super-123")
        ccl_resp = self.client.post(reverse("reservasi_cancel", args=[appr_res.pk]), {
            "alasan_pembatalan": "Acara dibatalkan oleh pembina."
        })
        self.assertRedirects(ccl_resp, reverse("reservasi_manage"))
        appr_res.refresh_from_db()
        self.assertEqual(appr_res.status, Reservasi.Status.CANCELLED)

        # Pastikan user dengan status NEEDS_REVISION menerima notifikasi bahwa jadwal telah tersedia kembali
        notif = Notifikasi.objects.filter(penerima=admin2, judul="Jadwal Fasilitas Tersedia Kembali").first()
        self.assertIsNotNone(notif)
        self.assertIn("sebelumnya disetujui telah dibatalkan", notif.pesan)

    def test_idor_protection_admin_cannot_edit_other_reservation(self):
        admin2 = User.objects.create_user(
            username="admin_other", password="password-kuat-123", nama="Admin Lain",
            email="other@example.com", role=User.Role.ADMIN,
        )
        res_admin1 = Reservasi.objects.create(
            pemohon=self.admin_user, fasilitas=self.fasilitas, tanggal=timezone.localdate() + timedelta(days=2),
            jam_mulai=time(10), jam_selesai=time(12), keperluan="Rapat Pribadi", status=Reservasi.Status.DRAFT,
        )

        self.client.login(username="admin_other", password="password-kuat-123")
        # Admin 2 mencoba edit reservasi Admin 1
        response = self.client.get(reverse("reservasi_update", args=[res_admin1.pk]))
        self.assertEqual(response.status_code, 404)

        # Admin 2 mencoba membatalkan reservasi Admin 1
        ccl_resp = self.client.post(reverse("reservasi_cancel", args=[res_admin1.pk]), {"alasan_pembatalan": "Batal"})
        self.assertEqual(ccl_resp.status_code, 404)

    def test_open_redirect_prevention(self):
        response = self.client.post(reverse("login") + "?next=https://evil.com/phishing", {
            "username": "admin1", "password": "password-kuat-123"
        })
        # Harus dialihkan ke dashboard, bukan domain luar
        self.assertRedirects(response, reverse("dashboard"))

    def test_xss_protection_in_detail_and_form(self):
        super_admin = User.objects.create_user(
            username="super_xss", password="password-super-123", nama="Super Admin XSS",
            email="superxss@example.com", role=User.Role.SUPER_ADMIN,
        )
        fasilitas_xss = Fasilitas.objects.create(
            nama_fasilitas="<script>alert('xss')</script>",
            kategori=Fasilitas.Kategori.RUANGAN,
            lokasi="Gedung XSS",
            kapasitas=10,
        )
        self.client.login(username="super_xss", password="password-super-123")

        # Cek fasilitas_detail: tidak boleh merender unescaped HTML dalam atribut onclick / inline
        res = self.client.get(reverse("fasilitas_detail", args=[fasilitas_xss.pk]))
        self.assertEqual(res.status_code, 200)
        # Nama fasilitas harus di-escape atau berada di data-confirm-item yang aman
        self.assertContains(res, 'data-confirm-item="&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"')

        # Cek reservasi_create: fasilitas-data JSON script harus meng-escape payload
        res_form = self.client.get(reverse("reservasi_create"))
        self.assertEqual(res_form.status_code, 200)
        self.assertContains(res_form, 'id="fasilitas-data"')
        self.assertNotContains(res_form, "<script>alert('xss')</script>;")


