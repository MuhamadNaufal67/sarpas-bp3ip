from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Fasilitas, Reservasi


SLOT_START_HOUR = 7
SLOT_END_HOUR = 18
SLOT_MINUTES = 30


def get_week_start(value=None):
    """Ambil hari Senin dari tanggal filter, atau dari minggu berjalan."""
    try:
        selected_date = datetime.strptime(value, "%Y-%m-%d").date() if value else timezone.localdate()
    except (TypeError, ValueError):
        selected_date = timezone.localdate()
    return selected_date - timedelta(days=selected_date.weekday())


def get_weekly_schedule(week_start, facility_id=None):
    """Susun grid Senin-Sabtu dari reservasi Disetujui, sekali per blok booking."""
    week_end = week_start + timedelta(days=5)
    reservasi = Reservasi.objects.filter(
        status=Reservasi.Status.APPROVED,
        tanggal__range=(week_start, week_end),
    ).select_related("fasilitas")
    if facility_id:
        reservasi = reservasi.filter(fasilitas_id=facility_id)
    reservasi = list(reservasi)

    days = [week_start + timedelta(days=index) for index in range(6)]
    slot_count = (SLOT_END_HOUR - SLOT_START_HOUR) * (60 // SLOT_MINUTES)
    grid = [[{"bookings": [], "rowspan": 1, "skip": False} for _ in days] for _ in range(slot_count)]

    for item in reservasi:
        day_index = (item.tanggal - week_start).days
        affected_slots = [
            index for index in range(slot_count)
            if item.jam_mulai < (datetime.combine(week_start, time(SLOT_START_HOUR)) + timedelta(minutes=(index + 1) * SLOT_MINUTES)).time()
            and item.jam_selesai > (datetime.combine(week_start, time(SLOT_START_HOUR)) + timedelta(minutes=index * SLOT_MINUTES)).time()
        ]
        if not affected_slots:
            continue
        start_index = affected_slots[0]
        cell = grid[start_index][day_index]
        if cell["skip"]:
            # Booking fasilitas lain dapat beririsan pada tampilan "Semua Fasilitas".
            # Tempelkan ke blok yang sudah menutup slot ini agar tidak hilang dari jadwal.
            for index in range(start_index - 1, -1, -1):
                parent = grid[index][day_index]
                if parent["bookings"] and index + parent["rowspan"] > start_index:
                    parent["bookings"].append(item)
                    break
            continue
        # Reservasi satu fasilitas tidak dapat bentrok karena validasi existing.
        # Bila beberapa fasilitas berbarengan, tampilkan dalam cell awal yang sama.
        if not cell["bookings"] and not any(grid[index][day_index]["skip"] for index in affected_slots):
            cell["rowspan"] = len(affected_slots)
            for index in affected_slots[1:]:
                grid[index][day_index]["skip"] = True
        cell["bookings"].append(item)

    rows = [
        {"label": "{} - {}".format(
            (datetime.combine(week_start, time(SLOT_START_HOUR)) + timedelta(minutes=index * SLOT_MINUTES)).strftime("%H:%M"),
            (datetime.combine(week_start, time(SLOT_START_HOUR)) + timedelta(minutes=(index + 1) * SLOT_MINUTES)).strftime("%H:%M"),
        ), "cells": grid[index]}
        for index in range(slot_count)
    ]
    return {"days": days, "rows": rows}


def schedule_context(request):
    facility_id = request.GET.get("fasilitas")
    if facility_id and not facility_id.isdigit():
        facility_id = None
    week_start = get_week_start(request.GET.get("minggu"))
    return {
        "week_start": week_start,
        "schedule": get_weekly_schedule(week_start, facility_id),
        "schedule_facilities": Fasilitas.objects.order_by("nama_fasilitas"),
        "selected_facility": int(facility_id) if facility_id else None,
    }
