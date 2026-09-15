from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Fasilitas, Notifikasi, Reservasi, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("SARPAS", {"fields": ("nama", "role", "created_at")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("SARPAS", {"fields": ("nama", "email", "role")}),)
    readonly_fields = ("created_at",)
    list_display = ("username", "nama", "email", "role", "is_active")
    list_filter = ("role", "is_active")


@admin.register(Fasilitas)
class FasilitasAdmin(admin.ModelAdmin):
    list_display = ("nama_fasilitas", "kategori", "lokasi", "kapasitas", "status")
    list_filter = ("kategori", "status")
    search_fields = ("nama_fasilitas", "lokasi")


@admin.register(Reservasi)
class ReservasiAdmin(admin.ModelAdmin):
    list_display = ("fasilitas", "pemohon", "tanggal", "jam_mulai", "jam_selesai", "status")
    list_filter = ("status", "tanggal")
    search_fields = ("fasilitas__nama_fasilitas", "pemohon__nama")


@admin.register(Notifikasi)
class NotifikasiAdmin(admin.ModelAdmin):
    list_display = ("judul", "penerima", "status_baca", "created_at")
    list_filter = ("status_baca",)
