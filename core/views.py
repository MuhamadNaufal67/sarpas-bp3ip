from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import CancelReservasiForm, FasilitasForm, RejectReservasiForm, ReservasiForm, fasilitas_tersedia
from .models import AuditLog, Fasilitas, Notifikasi, Reservasi, User
from .schedule import schedule_context


def kirim_notifikasi(penerima, judul, pesan):
    return Notifikasi.objects.create(penerima=penerima, judul=judul, pesan=pesan)


def catat_audit(request, aksi, entitas, objek, detail):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        aksi=aksi, entitas=entitas, entitas_id=getattr(objek, "pk", None), detail=detail,
    )


def kirim_ke_atasan(judul, pesan):
    for atasan in User.objects.filter(role=User.Role.ATASAN, is_active=True):
        kirim_notifikasi(atasan, judul, pesan)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "dashboard")
    return render(request, "registration/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    if request.user.role == User.Role.SUPER_ADMIN:
        semua = Reservasi.objects.select_related("fasilitas", "pemohon")
        context = {
            "total": semua.count(), "pending": semua.filter(status=Reservasi.Status.PENDING).count(),
            "approved": semua.filter(status=Reservasi.Status.APPROVED).count(),
            "rejected": semua.filter(status=Reservasi.Status.REJECTED).count(),
            "hari_ini": semua.filter(tanggal=timezone.localdate()).count(),
            "notifikasi_terbaru": request.user.notifikasi.all()[:5],
        }
        context.update(schedule_context(request))
        return render(request, "dashboard/super_admin.html", context)

    if request.user.role == User.Role.ADMIN:
        reservasi = Reservasi.objects.filter(pemohon=request.user)
        jadwal = Reservasi.objects.filter(status=Reservasi.Status.APPROVED).select_related("fasilitas")
        tanggal_filter = request.GET.get("tanggal")
        if tanggal_filter:
            jadwal = jadwal.filter(tanggal=tanggal_filter)
        context = {
            "total": reservasi.count(),
            "pending": reservasi.filter(status=Reservasi.Status.PENDING).count(),
            "approved": reservasi.filter(status=Reservasi.Status.APPROVED).count(),
            "rejected": reservasi.filter(status=Reservasi.Status.REJECTED).count(),
            "hari_ini": reservasi.filter(tanggal=timezone.localdate()).count(),
            "jadwal": jadwal,
            "tanggal_filter": tanggal_filter,
            "notifikasi_terbaru": request.user.notifikasi.all()[:5],
        }
        context.update(schedule_context(request))
        return render(request, "dashboard/admin_enhanced.html", context)

    pengajuan = Reservasi.objects.select_related("pemohon", "fasilitas")
    context = {
        "pending": pengajuan.filter(status=Reservasi.Status.PENDING).count(),
        "approved": pengajuan.filter(status=Reservasi.Status.APPROVED).count(),
        "rejected": pengajuan.filter(status=Reservasi.Status.REJECTED).count(),
        "pengajuan_terbaru": pengajuan[:8],
        "notifikasi_terbaru": request.user.notifikasi.all()[:5],
    }
    context.update(schedule_context(request))
    return render(request, "dashboard/atasan.html", context)


@role_required(User.Role.SUPER_ADMIN)
def fasilitas_list(request):
    return render(request, "facilities/list.html", {"fasilitas_list": Fasilitas.objects.all()})


@role_required(User.Role.SUPER_ADMIN)
def fasilitas_detail(request, pk):
    return render(request, "facilities/detail.html", {"fasilitas": get_object_or_404(Fasilitas, pk=pk)})


@role_required(User.Role.SUPER_ADMIN)
def fasilitas_create(request):
    form = FasilitasForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        catat_audit(request, "TAMBAH", "Fasilitas", form.instance, f"Menambahkan fasilitas {form.instance.nama_fasilitas}.")
        messages.success(request, "Fasilitas berhasil ditambahkan.")
        return redirect("fasilitas_list")
    return render(request, "facilities/form.html", {"form": form, "judul": "Tambah Fasilitas"})


@role_required(User.Role.SUPER_ADMIN)
def fasilitas_update(request, pk):
    fasilitas = get_object_or_404(Fasilitas, pk=pk)
    form = FasilitasForm(request.POST or None, instance=fasilitas)
    if request.method == "POST" and form.is_valid():
        form.save()
        catat_audit(request, "UBAH", "Fasilitas", fasilitas, f"Memperbarui fasilitas {fasilitas.nama_fasilitas}.")
        messages.success(request, "Fasilitas berhasil diperbarui.")
        return redirect("fasilitas_detail", pk=pk)
    return render(request, "facilities/form.html", {"form": form, "judul": "Edit Fasilitas"})


@require_POST
@role_required(User.Role.SUPER_ADMIN)
def fasilitas_delete(request, pk):
    fasilitas = get_object_or_404(Fasilitas, pk=pk)
    try:
        nama = fasilitas.nama_fasilitas
        fasilitas.delete()
        catat_audit(request, "HAPUS", "Fasilitas", fasilitas, f"Menghapus fasilitas {nama}.")
        messages.success(request, "Fasilitas berhasil dihapus.")
    except Exception:
        messages.error(request, "Fasilitas tidak dapat dihapus karena sudah dipakai dalam reservasi.")
    return redirect("fasilitas_list")


@role_required(User.Role.ADMIN)
def reservasi_list(request):
    reservasi = Reservasi.objects.filter(pemohon=request.user).select_related("fasilitas")
    return render(request, "reservations/list_enhanced.html", {"reservasi_list": reservasi})


@role_required(User.Role.ADMIN)
def reservasi_create(request):
    form = ReservasiForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reservasi = form.save(commit=False)
        reservasi.pemohon = request.user
        reservasi.status = Reservasi.Status.PENDING
        reservasi.save()
        catat_audit(request, "AJUKAN", "Reservasi", reservasi, f"Mengajukan reservasi {reservasi.fasilitas} pada {reservasi.tanggal}.")
        kirim_ke_atasan("Pengajuan reservasi baru", f"{request.user.nama} mengajukan {reservasi.fasilitas} pada {reservasi.tanggal}.")
        messages.success(request, "Pengajuan reservasi berhasil dikirim dan menunggu approval.")
        return redirect("reservasi_list")
    return render(request, "reservations/form.html", {"form": form, "judul": "Ajukan Reservasi"})


@role_required(User.Role.ADMIN)
def reservasi_update(request, pk):
    reservasi = get_object_or_404(Reservasi, pk=pk, pemohon=request.user)
    if reservasi.status not in [Reservasi.Status.DRAFT, Reservasi.Status.NEEDS_REVISION]:
        messages.error(request, "Hanya reservasi Draft atau Perlu Diperbaiki yang dapat diubah.")
        return redirect("reservasi_list")
    form = ReservasiForm(request.POST or None, instance=reservasi)
    if request.method == "POST" and form.is_valid():
        reservasi = form.save(commit=False)
        reservasi.status = Reservasi.Status.PENDING
        reservasi.alasan_penolakan = ""
        reservasi.save()
        catat_audit(request, "PERBAIKI", "Reservasi", reservasi, f"Memperbarui pengajuan reservasi {reservasi.fasilitas}.")
        kirim_ke_atasan("Pengajuan reservasi diperbarui", f"{request.user.nama} mengajukan kembali {reservasi.fasilitas} pada {reservasi.tanggal}.")
        messages.success(request, "Reservasi diperbarui dan dikirim kembali untuk approval.")
        return redirect("reservasi_list")
    return render(request, "reservations/form.html", {"form": form, "judul": "Perbaiki Reservasi"})


@require_POST
@role_required(User.Role.SUPER_ADMIN)
def reservasi_cancel(request, pk):
    reservasi = get_object_or_404(Reservasi.objects.select_related("fasilitas", "pemohon"), pk=pk)
    if reservasi.status not in (Reservasi.Status.PENDING, Reservasi.Status.APPROVED):
        messages.error(request, "Hanya reservasi Menunggu Approval atau Disetujui yang dapat dibatalkan.")
        return redirect("reservasi_manage")
    now = timezone.localtime()
    if reservasi.tanggal < timezone.localdate() or (reservasi.tanggal == timezone.localdate() and reservasi.jam_mulai <= now.time()):
        messages.error(request, "Reservasi yang sudah dimulai atau telah lewat tidak dapat dibatalkan.")
        return redirect("reservasi_manage")
    form = CancelReservasiForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Alasan pembatalan wajib diisi.")
        return redirect("reservasi_manage")
    reservasi.status = Reservasi.Status.CANCELLED
    reservasi.alasan_pembatalan = form.cleaned_data["alasan_pembatalan"]
    reservasi.save(update_fields=["status", "alasan_pembatalan", "updated_at"])
    catat_audit(request, "BATAL", "Reservasi", reservasi, f"Membatalkan reservasi {reservasi.fasilitas}; alasan: {reservasi.alasan_pembatalan}")
    kirim_notifikasi(reservasi.pemohon, "Reservasi dibatalkan", f"Reservasi {reservasi.fasilitas} pada {reservasi.tanggal} dibatalkan oleh Super Admin.")
    kirim_ke_atasan("Reservasi dibatalkan", f"{request.user.nama} membatalkan reservasi {reservasi.fasilitas} pada {reservasi.tanggal}.")
    messages.success(request, "Reservasi berhasil dibatalkan.")
    return redirect("reservasi_manage")


@role_required(User.Role.SUPER_ADMIN)
def reservasi_manage(request):
    reservasi = Reservasi.objects.select_related("pemohon", "fasilitas")
    return render(request, "reservations/manage.html", {"reservasi_list": reservasi, "cancel_form": CancelReservasiForm()})


@role_required(User.Role.SUPER_ADMIN)
def audit_log_list(request):
    return render(request, "audit/list.html", {"logs": AuditLog.objects.select_related("actor")[:200]})


@role_required(User.Role.ATASAN)
def pengajuan_list(request):
    pengajuan = Reservasi.objects.select_related("pemohon", "fasilitas")
    return render(request, "reservations/submissions_enhanced.html", {"pengajuan": pengajuan})


@role_required(User.Role.ATASAN)
def pengajuan_detail(request, pk):
    reservasi = get_object_or_404(Reservasi.objects.select_related("pemohon", "fasilitas"), pk=pk)
    return render(request, "reservations/detail_enhanced.html", {"reservasi": reservasi, "reject_form": RejectReservasiForm()})


@require_POST
@role_required(User.Role.ATASAN)
def pengajuan_approve(request, pk):
    with transaction.atomic():
        reservasi = get_object_or_404(Reservasi.objects.select_for_update().select_related("fasilitas", "pemohon"), pk=pk)
        if reservasi.status != Reservasi.Status.PENDING:
            messages.error(request, "Hanya pengajuan Menunggu Approval yang dapat diproses.")
            return redirect("pengajuan_detail", pk=pk)
        if not fasilitas_tersedia(reservasi.fasilitas, reservasi.tanggal, reservasi.jam_mulai, reservasi.jam_selesai, reservasi.pk):
            messages.error(request, "Fasilitas sudah disetujui untuk jadwal lain.")
            return redirect("pengajuan_detail", pk=pk)
        reservasi.status = Reservasi.Status.APPROVED
        reservasi.save()
        catat_audit(request, "SETUJUI", "Reservasi", reservasi, f"Menyetujui reservasi {reservasi.fasilitas} untuk {reservasi.pemohon.nama}.")
        kirim_notifikasi(reservasi.pemohon, "Reservasi disetujui", f"Reservasi {reservasi.fasilitas} pada {reservasi.tanggal} telah disetujui.")
        konflik = Reservasi.objects.filter(
            fasilitas=reservasi.fasilitas, tanggal=reservasi.tanggal, status=Reservasi.Status.PENDING,
            jam_mulai__lt=reservasi.jam_selesai, jam_selesai__gt=reservasi.jam_mulai,
        ).exclude(pk=reservasi.pk).select_related("pemohon")
        for item in konflik:
            item.status = Reservasi.Status.NEEDS_REVISION
            item.save(update_fields=["status", "updated_at"])
            kirim_notifikasi(item.pemohon, "Reservasi perlu diperbaiki", "Reservasi yang Anda ajukan tidak dapat diproses karena fasilitas telah disetujui untuk reservasi lain pada waktu yang sama. Silakan memilih jadwal atau fasilitas lain.")
    messages.success(request, "Reservasi disetujui. Pengajuan yang bentrok telah ditandai.")
    return redirect("pengajuan_detail", pk=pk)


@require_POST
@role_required(User.Role.ATASAN)
def pengajuan_reject(request, pk):
    reservasi = get_object_or_404(Reservasi.objects.select_related("pemohon"), pk=pk)
    if reservasi.status != Reservasi.Status.PENDING:
        messages.error(request, "Hanya pengajuan Menunggu Approval yang dapat diproses.")
        return redirect("pengajuan_detail", pk=pk)
    form = RejectReservasiForm(request.POST)
    if not form.is_valid():
        return render(request, "reservations/detail_enhanced.html", {"reservasi": reservasi, "reject_form": form})
    reservasi.status = Reservasi.Status.REJECTED
    reservasi.alasan_penolakan = form.cleaned_data["alasan_penolakan"]
    reservasi.save(update_fields=["status", "alasan_penolakan", "updated_at"])
    catat_audit(request, "TOLAK", "Reservasi", reservasi, f"Menolak reservasi {reservasi.fasilitas}; alasan: {reservasi.alasan_penolakan}")
    kirim_notifikasi(reservasi.pemohon, "Reservasi ditolak", f"Reservasi Anda ditolak. Alasan: {reservasi.alasan_penolakan}")
    messages.success(request, "Reservasi telah ditolak.")
    return redirect("pengajuan_detail", pk=pk)


@login_required
def notifikasi_list(request):
    return render(request, "notifications/list.html", {"notifikasi_list": request.user.notifikasi.all()})


@require_POST
@login_required
def notifikasi_baca(request, pk):
    notifikasi = get_object_or_404(Notifikasi, pk=pk, penerima=request.user)
    notifikasi.status_baca = True
    notifikasi.save(update_fields=["status_baca"])
    return redirect("notifikasi_list")

# Create your views here.
