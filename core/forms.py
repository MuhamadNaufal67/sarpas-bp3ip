from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Fasilitas, Reservasi, User


JAM_OPERASIONAL_MULAI = 7
JAM_OPERASIONAL_SELESAI = 18


def fasilitas_tersedia(fasilitas, tanggal, jam_mulai, jam_selesai, exclude_id=None):
    """True bila tidak ada reservasi yang sudah disetujui pada waktu bertumpang tindih."""
    konflik = Reservasi.objects.filter(
        fasilitas=fasilitas,
        tanggal=tanggal,
        status=Reservasi.Status.APPROVED,
        jam_mulai__lt=jam_selesai,
        jam_selesai__gt=jam_mulai,
    )
    if exclude_id:
        konflik = konflik.exclude(pk=exclude_id)
    return not konflik.exists()


class FasilitasForm(forms.ModelForm):
    kapasitas = forms.IntegerField(
        min_value=1,
        error_messages={
            "min_value": "Kapasitas fasilitas minimal 1 orang.",
            "invalid": "Masukkan angka yang valid untuk kapasitas.",
            "required": "Kapasitas fasilitas wajib diisi.",
        },
        widget=forms.NumberInput(attrs={"min": "1", "step": "1", "placeholder": "Contoh: 30"}),
    )

    class Meta:
        model = Fasilitas
        fields = ["nama_fasilitas", "kategori", "lokasi", "kapasitas", "deskripsi", "status", "keterangan_tambahan"]
        widgets = {
            "nama_fasilitas": forms.TextInput(attrs={"placeholder": "Nama ruangan / lab"}),
            "lokasi": forms.TextInput(attrs={"placeholder": "Contoh: Gedung A Lantai 2"}),
            "deskripsi": forms.Textarea(attrs={"rows": 3, "placeholder": "Deskripsi umum fasilitas"}),
            "keterangan_tambahan": forms.Textarea(attrs={"rows": 3, "placeholder": "Spesifikasi alat, AC, proyektor, dll."}),
        }

    def clean_nama_fasilitas(self):
        nama = self.cleaned_data.get("nama_fasilitas", "").strip()
        if not nama:
            raise ValidationError("Nama fasilitas tidak boleh kosong.")
        qs = Fasilitas.objects.filter(nama_fasilitas__iexact=nama)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Nama fasilitas sudah terdaftar. Gunakan nama yang berbeda.")
        return nama

    def clean_lokasi(self):
        lokasi = self.cleaned_data.get("lokasi", "").strip()
        if not lokasi:
            raise ValidationError("Lokasi fasilitas tidak boleh kosong.")
        return lokasi

    def clean_deskripsi(self):
        return self.cleaned_data.get("deskripsi", "").strip()

    def clean_keterangan_tambahan(self):
        return self.cleaned_data.get("keterangan_tambahan", "").strip()


class ReservasiForm(forms.ModelForm):
    class Meta:
        model = Reservasi
        fields = ["fasilitas", "tanggal", "jam_mulai", "jam_selesai", "keperluan", "keterangan"]
        widgets = {
            "tanggal": forms.DateInput(attrs={"type": "date"}),
            "jam_mulai": forms.TimeInput(attrs={"type": "time", "step": "1800", "min": "07:00", "max": "18:00"}),
            "jam_selesai": forms.TimeInput(attrs={"type": "time", "step": "1800", "min": "07:00", "max": "18:00"}),
            "keperluan": forms.TextInput(attrs={"placeholder": "Contoh: Diklat Pelaut Tingkat II"}),
            "keterangan": forms.Textarea(attrs={"rows": 3, "placeholder": "Kebutuhan tambahan seperti perlengkapan audio/visual (opsional)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fasilitas"].queryset = Fasilitas.objects.filter(status=Fasilitas.Status.AKTIF)
        self.fields["fasilitas"].empty_label = "-- Pilih Fasilitas Aktif --"

    def clean_keperluan(self):
        keperluan = self.cleaned_data.get("keperluan", "").strip()
        if not keperluan:
            raise ValidationError("Keperluan reservasi tidak boleh kosong.")
        return keperluan

    def clean_keterangan(self):
        return self.cleaned_data.get("keterangan", "").strip()

    def clean(self):
        cleaned_data = super().clean()
        fasilitas = cleaned_data.get("fasilitas")
        tanggal = cleaned_data.get("tanggal")
        jam_mulai = cleaned_data.get("jam_mulai")
        jam_selesai = cleaned_data.get("jam_selesai")

        if fasilitas and fasilitas.status != Fasilitas.Status.AKTIF:
            self.add_error("fasilitas", "Fasilitas yang dipilih tidak aktif.")
        if jam_mulai and jam_selesai and jam_selesai <= jam_mulai:
            self.add_error("jam_selesai", "Jam selesai harus lebih besar dari jam mulai.")
        if fasilitas and tanggal and jam_mulai and jam_selesai and jam_selesai > jam_mulai:
            if not fasilitas_tersedia(fasilitas, tanggal, jam_mulai, jam_selesai, self.instance.pk):
                self.add_error(None, "Fasilitas tidak tersedia pada waktu tersebut.")
        if tanggal and tanggal < timezone.localdate():
            self.add_error("tanggal", "Reservasi tidak dapat dibuat untuk tanggal yang sudah lewat.")
        if tanggal and tanggal.weekday() == 6:
            self.add_error("tanggal", "Reservasi hanya dapat dilakukan pada Senin sampai Sabtu.")
        if jam_mulai and jam_mulai.hour < JAM_OPERASIONAL_MULAI:
            self.add_error("jam_mulai", "Jam operasional dimulai pukul 07.00.")
        if jam_selesai and (jam_selesai.hour > JAM_OPERASIONAL_SELESAI or (jam_selesai.hour == JAM_OPERASIONAL_SELESAI and jam_selesai.minute > 0)):
            self.add_error("jam_selesai", "Jam operasional berakhir pukul 18.00.")
        for field_name, nilai in (("jam_mulai", jam_mulai), ("jam_selesai", jam_selesai)):
            if nilai and (nilai.minute not in (0, 30) or nilai.second or nilai.microsecond):
                self.add_error(field_name, "Pilih waktu dalam interval 30 menit.")
        return cleaned_data


class RejectReservasiForm(forms.Form):
    alasan_penolakan = forms.CharField(
        label="Alasan penolakan",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Tuliskan alasan penolakan secara jelas"}),
        error_messages={"required": "Alasan penolakan wajib diisi."},
    )

    def clean_alasan_penolakan(self):
        alasan = self.cleaned_data.get("alasan_penolakan", "").strip()
        if not alasan:
            raise ValidationError("Alasan penolakan tidak boleh kosong.")
        return alasan


class CancelReservasiForm(forms.Form):
    alasan_pembatalan = forms.CharField(
        label="Alasan pembatalan",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Tuliskan alasan pembatalan reservasi"}),
        error_messages={"required": "Alasan pembatalan wajib diisi."},
    )

    def clean_alasan_pembatalan(self):
        alasan = self.cleaned_data.get("alasan_pembatalan", "").strip()
        if not alasan:
            raise ValidationError("Alasan pembatalan tidak boleh kosong.")
        return alasan


class AdminCreateForm(forms.ModelForm):
    """Form untuk Super Admin membuat akun Admin baru."""
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Masukkan password baru", "autocomplete": "new-password"}),
        help_text="Password harus memenuhi kebijakan keamanan sistem.",
    )
    password2 = forms.CharField(
        label="Konfirmasi Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Ulangi password", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["username", "nama", "email"]
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Contoh: admin.budi", "autocomplete": "off"}),
            "nama": forms.TextInput(attrs={"placeholder": "Contoh: Budi Santoso"}),
            "email": forms.EmailInput(attrs={"placeholder": "Contoh: budi@bp3ip.go.id"}),
        }
        help_texts = {
            "username": "Username harus unik. Gunakan huruf kecil, angka, dan tanda titik/garis bawah.",
        }

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if not username:
            raise ValidationError("Username tidak boleh kosong.")
        if User.objects.filter(username=username).exists():
            raise ValidationError("Username sudah digunakan. Pilih username lain.")
        return username

    def clean_nama(self):
        nama = self.cleaned_data.get("nama", "").strip()
        if not nama:
            raise ValidationError("Nama lengkap tidak boleh kosong.")
        return nama

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise ValidationError("Email tidak boleh kosong.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("Email sudah terdaftar.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1:
            validate_password(password1)
        return password1

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Konfirmasi password tidak cocok.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.role = User.Role.ADMIN
        user.is_active = True
        if commit:
            user.save()
        return user
