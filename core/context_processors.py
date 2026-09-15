def notification_badge(request):
    """Jumlah notifikasi belum dibaca untuk badge sidebar user yang sedang login."""
    if request.user.is_authenticated:
        return {"unread_notification_count": request.user.notifikasi.filter(status_baca=False).count()}
    return {"unread_notification_count": 0}
