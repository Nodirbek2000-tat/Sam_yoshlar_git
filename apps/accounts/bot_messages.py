"""Shaxsiy Telegram xabarlari — sayt navbatga qo'yadi, bot yuboradi.

Sayt Telegram'ga o'zi ulanmaydi (bot tokeni faqat botda). Shuning uchun
xabar `BotMessage` navbatiga tushadi, bot uni bir necha soniyada olib
egasiga yetkazadi.
"""

from .bot_feed import site_link
from .models import BotMessage


def send_personal(user, text, buttons=()):
    """Foydalanuvchiga botdan xabar. Telegram'i ulanmagan bo'lsa — jim o'tadi.

    `buttons` — `[{'text': ..., 'url': ...}]`; `url` sayt ichidagi yo'l
    (`/kabinet/...`) bo'lsa, to'liq manzilga aylantiriladi.
    """
    telegram_id = getattr(user, 'telegram_id', None)
    if not telegram_id or telegram_id <= 0:
        return None

    ready = []
    for button in buttons:
        url = button['url']
        if url.startswith('/'):
            url = site_link(url)
        # Telegram tugmasi faqat to'liq https manzilni qabul qiladi
        if url.startswith('https://'):
            ready.append({'text': button['text'], 'url': url})

    return BotMessage.objects.create(telegram_id=telegram_id, text=text, buttons=ready)
