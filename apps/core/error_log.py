"""Server xatolarini bazaga yozish.

`settings.LOGGING` dagi `django.request` loggeriga ulanadi: foydalanuvchi
500 xatoga duch kelsa, u shu yerga tushadi. Bir xil xato (turi va kodning
aynan o'sha qatori) bitta yozuv bo'lib qoladi — faqat soni va oxirgi vaqti
yangilanadi. Panelda «Server xatolari» sahifasida ko'rinadi, bot esa
adminlarga Telegram'da xabar beradi.

Loglash hech qachon saytni yiqitmasligi kerak: baza ishlamasa ham xato
jimgina o'tkazib yuboriladi (u baribir Docker logida qoladi).
"""

import hashlib
import logging
import threading
import traceback as tb

from django.db import transaction
from django.db.models import F
from django.utils import timezone

#: Traceback shundan uzun bo'lsa, oxiri saqlanadi (eng muhimi — oxirida)
TRACEBACK_LIMIT = 8000

_local = threading.local()


def _signature(exc_type, exc_value, frames):
    """Bir xil xatoni tanish: turi + bizning koddagi oxirgi qator."""
    ours = [frame for frame in frames if '/apps/' in frame.filename.replace('\\', '/')]
    frame = (ours or frames or [None])[-1]
    where = f"{frame.filename}:{frame.lineno}" if frame else ''
    raw = f"{exc_type.__name__}|{where}" if frame else f"{exc_type.__name__}|{exc_value}"
    return hashlib.sha1(raw.encode('utf-8', 'replace')).hexdigest(), where


def _short_location(where):
    """`/app/apps/api/views.py:123` -> `apps/api/views.py:123`"""
    path = where.replace('\\', '/')
    return path[path.find('apps/'):] if 'apps/' in path else path[-200:]


def record_error(exc_info, request=None):
    """Xatoni bazaga yozadi (yoki borini yangilaydi). Hech qachon xato chiqarmaydi."""
    # Yozish paytida yana xato chiqsa — cheksiz aylanib qolmasin
    if getattr(_local, 'busy', False):
        return
    _local.busy = True

    try:
        from .models import ServerError

        exc_type, exc_value, exc_tb = exc_info
        frames = tb.extract_tb(exc_tb) if exc_tb else []
        signature, where = _signature(exc_type, exc_value, frames)

        text = ''.join(tb.format_exception(exc_type, exc_value, exc_tb))
        if len(text) > TRACEBACK_LIMIT:
            text = '…\n' + text[-TRACEBACK_LIMIT:]

        title = f"{exc_type.__name__}: {exc_value}"[:300]
        now = timezone.now()
        method = getattr(request, 'method', '') or ''
        path = request.get_full_path()[:500] if request is not None else ''

        with transaction.atomic():
            updated = ServerError.objects.filter(signature=signature).update(
                count=F('count') + 1, last_seen=now, title=title, method=method,
                path=path, traceback=text)
            if not updated:
                ServerError.objects.create(
                    signature=signature, title=title, location=_short_location(where),
                    method=method, path=path, traceback=text, first_seen=now, last_seen=now)
    except Exception:                               # noqa: BLE001 — loglash saytni yiqitmasin
        pass
    finally:
        _local.busy = False


class DatabaseErrorHandler(logging.Handler):
    """`django.request` dagi xatolarni (`exc_info` bilan) bazaga yozadi."""

    def emit(self, record):
        if not record.exc_info or record.exc_info[0] is None:
            return
        record_error(record.exc_info, getattr(record, 'request', None))
