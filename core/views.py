import json
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import (
    AdminCreateForm,
    CancelReservasiForm,
    FasilitasForm,
    RejectReservasiForm,
    ReservasiForm,
    fasilitas_tersedia,
)
from .models import AuditLog, Fasilitas, Notifikasi, Reservasi, User, _generate_kode_reservasi
from .schedule import schedule_context


ITEMS_PER_PAGE = 10


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
        next_url = request.POST.get("next") or request.GET.get("next")
        if not (next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})):
            next_url = "dashboard"
        return redirect(next_url)
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
        context = {
            "total": reservasi.count(),
            "pending": reservasi.filter(status=Reservasi.Status.PENDING).count(),
            "approved": reservasi.filter(status=Reservasi.Status.APPROVED).count(),
            "rejected": reservasi.filter(status=Reservasi.Status.REJECTED).count(),
            "hari_ini": reservasi.filter(tanggal=timezone.localdate()).count(),
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
    qs = Fasilitas.objects.all().order_by("nama_fasilitas")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(nama_fasilitas__icontains=q)
            | Q(kategori__icontains=q)
            | Q(lokasi__icontains=q)
            | Q(deskripsi__icontains=q)
            | Q(status__icontains=q)
            | Q(keterangan_tambahan__icontains=q)
        )
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "facilities/list.html", {
        "fasilitas_list": page_obj,
        "page_obj": page_obj,
        "q": q,
    })


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
    except ProtectedError:
        messages.error(request, "Fasilitas tidak dapat dihapus karena sudah dipakai dalam reservasi.")
    return redirect("fasilitas_list")


@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
def reservasi_list(request):
    """Daftar reservasi milik Admin yang sedang login, dengan search dan pagination."""
    qs = Reservasi.objects.filter(pemohon=request.user).select_related("fasilitas")

    q = request.GET.get("q", "").strip()
    tanggal = request.GET.get("tanggal", "").strip()
    
    if q:
        qs = qs.filter(
            Q(kode_reservasi__icontains=q)
            | Q(fasilitas__nama_fasilitas__icontains=q)
            | Q(fasilitas__kategori__icontains=q)
            | Q(status__icontains=q)
            | Q(keperluan__icontains=q)
        )
    if tanggal:
        try:
            qs = qs.filter(tanggal=tanggal)
        except (ValueError, TypeError):
            pass

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "reservations/list_enhanced.html", {
        "reservasi_list": page_obj,
        "page_obj": page_obj,
        "cancel_form": CancelReservasiForm(),
        "q": q,
        "tanggal": tanggal,
    })


def _get_fasilitas_list():
    return list(
        Fasilitas.objects.filter(status=Fasilitas.Status.AKTIF)
        .order_by("nama_fasilitas")
        .values("id", "nama_fasilitas", "kategori", "kapasitas", "lokasi")
    )


def _get_fasilitas_json():
    return json.dumps(_get_fasilitas_list())


@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
def reservasi_create(request):
    form = ReservasiForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            reservasi = form.save(commit=False)
            reservasi.pemohon = request.user
            reservasi.status = Reservasi.Status.PENDING
            
            # Lock baris reservasi terkait fasilitas ini untuk mencegah race condition
            list(Reservasi.objects.select_for_update().filter(fasilitas=reservasi.fasilitas))
            
            # Generate kode reservasi secara aman
            reservasi.kode_reservasi = _generate_kode_reservasi(reservasi.fasilitas)
            reservasi.save()

        catat_audit(request, "AJUKAN", "Reservasi", reservasi,
                    f"Mengajukan reservasi {reservasi.fasilitas} pada {reservasi.tanggal}. Kode: {reservasi.kode_reservasi}")
        kirim_ke_atasan(
            "Pengajuan reservasi baru",
            f"{request.user.nama} mengajukan {reservasi.fasilitas} pada {reservasi.tanggal}. Kode: {reservasi.kode_reservasi}"
        )
        messages.success(request, f"Pengajuan reservasi berhasil dikirim. Kode Reservasi Anda: {reservasi.kode_reservasi}")
        return redirect("reservasi_list")
        
    fas_list = _get_fasilitas_list()
    return render(request, "reservations/form.html", {
        "form": form,
        "judul": "Ajukan Reservasi",
        "fasilitas_json": json.dumps(fas_list),
        "fasilitas_list_data": fas_list,
    })


@role_required(User.Role.ADMIN, User.Role.SUPER_ADMIN)
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
        # Kode reservasi TIDAK diubah saat revisi.
        reservasi.save()
        catat_audit(request, "PERBAIKI", "Reservasi", reservasi, f"Memperbarui pengajuan reservasi {reservasi.fasilitas}.")
        kirim_ke_atasan("Pengajuan reservasi diperbarui", f"{request.user.nama} mengajukan kembali {reservasi.fasilitas} pada {reservasi.tanggal}.")
        messages.success(request, "Reservasi diperbarui dan dikirim kembali untuk approval.")
        return redirect("reservasi_list")
    fas_list = _get_fasilitas_list()
    return render(request, "reservations/form.html", {
        "form": form,
        "judul": "Perbaiki Reservasi",
        "fasilitas_json": json.dumps(fas_list),
        "fasilitas_list_data": fas_list,
    })


@require_POST
@login_required
def reservasi_cancel(request, pk):
    if request.user.role == User.Role.SUPER_ADMIN:
        reservasi = get_object_or_404(Reservasi.objects.select_related("fasilitas", "pemohon"), pk=pk)
        redirect_name = "reservasi_manage"
    elif request.user.role == User.Role.ADMIN:
        reservasi = get_object_or_404(Reservasi.objects.select_related("fasilitas", "pemohon"), pk=pk, pemohon=request.user)
        redirect_name = "reservasi_list"
    else:
        messages.error(request, "Anda tidak memiliki akses untuk membatalkan reservasi.")
        return redirect("dashboard")

    if request.user.role == User.Role.ADMIN and reservasi.status != Reservasi.Status.PENDING:
        messages.error(request, "Hanya pengajuan dengan status Menunggu Approval yang dapat Anda batalkan.")
        return redirect(redirect_name)

    if request.user.role == User.Role.SUPER_ADMIN and reservasi.status not in (Reservasi.Status.PENDING, Reservasi.Status.APPROVED):
        messages.error(request, "Hanya reservasi Menunggu Approval atau Disetujui yang dapat dibatalkan.")
        return redirect(redirect_name)

    now = timezone.localtime()
    if reservasi.tanggal < timezone.localdate() or (reservasi.tanggal == timezone.localdate() and reservasi.jam_mulai <= now.time()):
        messages.error(request, "Reservasi yang sudah dimulai atau telah lewat tidak dapat dibatalkan.")
        return redirect(redirect_name)

    form = CancelReservasiForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Alasan pembatalan wajib diisi.")
        return redirect(redirect_name)

    was_approved = reservasi.status == Reservasi.Status.APPROVED
    reservasi.status = Reservasi.Status.CANCELLED
    reservasi.alasan_pembatalan = form.cleaned_data["alasan_pembatalan"]
    reservasi.save(update_fields=["status", "alasan_pembatalan", "updated_at"])
    catat_audit(request, "BATAL", "Reservasi", reservasi, f"Membatalkan reservasi {reservasi.fasilitas}; alasan: {reservasi.alasan_pembatalan}")
    if request.user.role == User.Role.SUPER_ADMIN:
        kirim_notifikasi(reservasi.pemohon, "Reservasi dibatalkan", f"Reservasi {reservasi.fasilitas} pada {reservasi.tanggal} dibatalkan oleh Super Admin.")
    kirim_ke_atasan("Reservasi dibatalkan", f"{request.user.nama} membatalkan reservasi {reservasi.fasilitas} pada {reservasi.tanggal}.")

    if was_approved:
        # Beri tahu pemohon yang status reservasinya sebelumnya NEEDS_REVISION karena bentrok
        konflik_revisi = Reservasi.objects.filter(
            fasilitas=reservasi.fasilitas,
            tanggal=reservasi.tanggal,
            status=Reservasi.Status.NEEDS_REVISION,
            jam_mulai__lt=reservasi.jam_selesai,
            jam_selesai__gt=reservasi.jam_mulai,
        ).select_related("pemohon")
        for item in konflik_revisi:
            kirim_notifikasi(
                item.pemohon,
                "Jadwal Fasilitas Tersedia Kembali",
                f"Reservasi {reservasi.fasilitas} pada {reservasi.tanggal} ({reservasi.jam_mulai.strftime('%H:%M')} - {reservasi.jam_selesai.strftime('%H:%M')}) yang sebelumnya disetujui telah dibatalkan. Anda dapat mengedit dan mengajukan kembali permohonan reservasi Anda."
            )

    messages.success(request, "Reservasi berhasil dibatalkan.")
    return redirect(redirect_name)


@role_required(User.Role.SUPER_ADMIN)
def reservasi_manage(request):
    qs = Reservasi.objects.select_related("pemohon", "fasilitas").order_by("-tanggal", "jam_mulai")
    q = request.GET.get("q", "").strip()
    tanggal = request.GET.get("tanggal", "").strip()
    
    if q:
        qs = qs.filter(
            Q(kode_reservasi__icontains=q)
            | Q(pemohon__nama__icontains=q)
            | Q(pemohon__username__icontains=q)
            | Q(fasilitas__nama_fasilitas__icontains=q)
            | Q(fasilitas__kategori__icontains=q)
            | Q(status__icontains=q)
            | Q(keperluan__icontains=q)
        )
    if tanggal:
        try:
            qs = qs.filter(tanggal=tanggal)
        except (ValueError, TypeError):
            pass
            
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "reservations/manage.html", {
        "reservasi_list": page_obj,
        "page_obj": page_obj,
        "cancel_form": CancelReservasiForm(),
        "q": q,
        "tanggal": tanggal,
    })


@role_required(User.Role.SUPER_ADMIN)
def audit_log_list(request):
    qs = AuditLog.objects.select_related("actor").order_by("-created_at")
    q = request.GET.get("q", "").strip()
    tanggal = request.GET.get("tanggal", "").strip()

    if q:
        qs = qs.filter(
            Q(aksi__icontains=q)
            | Q(entitas__icontains=q)
            | Q(detail__icontains=q)
            | Q(actor__nama__icontains=q)
            | Q(actor__username__icontains=q)
        )
    if tanggal:
        try:
            qs = qs.filter(created_at__date=tanggal)
        except (ValueError, TypeError):
            pass

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "audit/list.html", {
        "logs": page_obj,
        "page_obj": page_obj,
        "q": q,
        "tanggal": tanggal,
    })


@role_required(User.Role.ATASAN)
def pengajuan_list(request):
    """Daftar semua pengajuan reservasi untuk Atasan, dengan search dan pagination."""
    qs = Reservasi.objects.select_related("pemohon", "fasilitas").order_by("-tanggal", "jam_mulai")

    q = request.GET.get("q", "").strip()
    tanggal = request.GET.get("tanggal", "").strip()
    
    if q:
        qs = qs.filter(
            Q(kode_reservasi__icontains=q)
            | Q(pemohon__nama__icontains=q)
            | Q(pemohon__username__icontains=q)
            | Q(fasilitas__nama_fasilitas__icontains=q)
            | Q(fasilitas__kategori__icontains=q)
            | Q(status__icontains=q)
            | Q(keperluan__icontains=q)
        )
    if tanggal:
        try:
            qs = qs.filter(tanggal=tanggal)
        except (ValueError, TypeError):
            pass

    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "reservations/submissions_enhanced.html", {
        "pengajuan": page_obj,
        "page_obj": page_obj,
        "q": q,
        "tanggal": tanggal,
    })


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
    qs = request.user.notifikasi.all().order_by("-created_at")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(judul__icontains=q)
            | Q(pesan__icontains=q)
        )
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "notifications/list.html", {
        "notifikasi_list": page_obj,
        "page_obj": page_obj,
        "q": q,
    })


@require_POST
@login_required
def notifikasi_baca(request, pk):
    notifikasi = get_object_or_404(Notifikasi, pk=pk, penerima=request.user)
    notifikasi.status_baca = True
    notifikasi.save(update_fields=["status_baca"])
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if not (next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})):
        next_url = "notifikasi_list"
    return redirect(next_url)


@require_POST
@login_required
def notifikasi_baca_semua(request):
    request.user.notifikasi.filter(status_baca=False).update(status_baca=True)
    messages.success(request, "Semua notifikasi telah ditandai sebagai sudah dibaca.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if not (next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()})):
        next_url = "notifikasi_list"
    return redirect(next_url)


@require_POST
@login_required
def notifikasi_tandai_semua_dibaca(request):
    """Tandai notifikasi belum dibaca milik pengguna yang sedang login."""
    jumlah_ditandai = request.user.notifikasi.filter(status_baca=False).update(status_baca=True)
    return JsonResponse({"marked_count": jumlah_ditandai})


# ── Super Admin: Kelola Akun Admin ─────────────────────────────────────────

@role_required(User.Role.SUPER_ADMIN)
def admin_list(request):
    """Daftar seluruh akun dengan role Admin, dengan search dan pagination."""
    qs = User.objects.filter(role=User.Role.ADMIN).order_by("nama")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(nama__icontains=q)
            | Q(email__icontains=q)
        )
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "accounts/admin_list.html", {
        "admin_users": page_obj,
        "page_obj": page_obj,
        "q": q,
    })


@role_required(User.Role.SUPER_ADMIN)
def admin_create(request):
    """Form pembuatan akun Admin baru oleh Super Admin."""
    form = AdminCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        new_admin = form.save()
        catat_audit(
            request, "BUAT_ADMIN", "User", new_admin,
            f"Super Admin membuat akun Admin baru: {new_admin.username} ({new_admin.nama})."
        )
        messages.success(request, f"Akun Admin '{new_admin.username}' berhasil dibuat.")
        return redirect("admin_list")
    return render(request, "accounts/admin_create.html", {"form": form})
