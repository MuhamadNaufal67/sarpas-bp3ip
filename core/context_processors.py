def notification_badge(request):
    """Jumlah notifikasi belum dibaca dan daftar notifikasi ringkas untuk dropdown header user login."""
    if request.user.is_authenticated:
        return {
            "unread_notification_count": request.user.notifikasi.filter(status_baca=False).count(),
            "header_recent_notifications": request.user.notifikasi.all()[:5],
        }
    return {"unread_notification_count": 0, "header_recent_notifications": []}
