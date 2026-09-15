from django import forms
from django.core.exceptions import ValidationError

from .models import Fasilitas, Reservasi


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
    class Meta:
        model = Fasilitas
        fields = ["nama_fasilitas", "kategori", "lokasi", "kapasitas", "deskripsi", "status", "keterangan_tambahan"]
        widgets = {"deskripsi": forms.Textarea(attrs={"rows": 3}), "keterangan_tambahan": forms.Textarea(attrs={"rows": 3})}


class ReservasiForm(forms.ModelForm):
    class Meta:
        model = Reservasi
        fields = ["fasilitas", "tanggal", "jam_mulai", "jam_selesai", "keperluan", "keterangan"]
        widgets = {
            "tanggal": forms.DateInput(attrs={"type": "date"}),
            "jam_mulai": forms.TimeInput(attrs={"type": "time"}),
            "jam_selesai": forms.TimeInput(attrs={"type": "time"}),
            "keterangan": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fasilitas"].queryset = Fasilitas.objects.filter(status=Fasilitas.Status.AKTIF)

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
                raise ValidationError("Fasilitas tidak tersedia pada waktu tersebut.")
        return cleaned_data


class RejectReservasiForm(forms.Form):
    alasan_penolakan = forms.CharField(
        label="Alasan penolakan",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Tuliskan alasan penolakan"}),
    )
