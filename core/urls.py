from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("fasilitas/", views.fasilitas_list, name="fasilitas_list"),
    path("fasilitas/tambah/", views.fasilitas_create, name="fasilitas_create"),
    path("fasilitas/<int:pk>/", views.fasilitas_detail, name="fasilitas_detail"),
    path("fasilitas/<int:pk>/edit/", views.fasilitas_update, name="fasilitas_update"),
    path("fasilitas/<int:pk>/hapus/", views.fasilitas_delete, name="fasilitas_delete"),
    path("reservasi/", views.reservasi_list, name="reservasi_list"),
    path("reservasi/tambah/", views.reservasi_create, name="reservasi_create"),
    path("reservasi/<int:pk>/edit/", views.reservasi_update, name="reservasi_update"),
    path("reservasi/<int:pk>/batal/", views.reservasi_cancel, name="reservasi_cancel"),
    path("manajemen-reservasi/", views.reservasi_manage, name="reservasi_manage"),
    path("audit-log/", views.audit_log_list, name="audit_log_list"),
    path("pengajuan/", views.pengajuan_list, name="pengajuan_list"),
    path("pengajuan/<int:pk>/", views.pengajuan_detail, name="pengajuan_detail"),
    path("pengajuan/<int:pk>/approve/", views.pengajuan_approve, name="pengajuan_approve"),
    path("pengajuan/<int:pk>/reject/", views.pengajuan_reject, name="pengajuan_reject"),
    path("notifikasi/", views.notifikasi_list, name="notifikasi_list"),
    path("notifikasi/<int:pk>/baca/", views.notifikasi_baca, name="notifikasi_baca"),
    path("notifikasi/tandai-semua-dibaca/", views.notifikasi_tandai_semua_dibaca, name="notifikasi_tandai_semua_dibaca"),
    # Super Admin — Kelola Akun Admin
    path("kelola-akun/", views.admin_list, name="admin_list"),
    path("kelola-akun/tambah/", views.admin_create, name="admin_create"),
]
