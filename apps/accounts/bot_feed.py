"""Saytga yangi narsa qo'shilsa — botga yuborish navbatiga qo'shadi.

Yangilik, e'lon, startap, tadbirkor, chet eldagi tengdosh yoki tashkilot
muammosi chiqqanda
shu yerdagi qabul qiluvchilar ishlaydi. Panelda «Botga yuborish» o'chiq
bo'lsa — navbatga hech narsa tushmaydi.

Navbatni botning o'zi olib, hamma foydalanuvchiga yuboradi: rasm, matn
boshlanishi va «Davomini o'qish» tugmasi.
"""

import re

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.constants import Status

from .models import BotPost, BotSetting

#: Xabar boshlanishi — botda shuncha belgi ko'rinadi
EXCERPT_LIMIT = 300


def site_link(path):
    base = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    return f"{base}{path}"


def file_url(field):
    if not field:
        return ''
    return site_link(field.url)


#: E'lon matnidagi bezash belgilari: # sarlavha, **qalin**, [havola](url), >> ...
_LINK = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_MARKS = re.compile(r'(^|\n)\s*(#{1,3}\s+|>>\s*|-\s+|---+\s*$)', re.MULTILINE)


def plain_text(text):
    """Bezash belgilarisiz oddiy matn — botda «**» ko'rinib qolmasin."""
    text = _LINK.sub(r'\1', text or '')
    text = _MARKS.sub(r'\1', text)
    return text.replace('**', '').replace('*', '')


def shorten(text, limit=EXCERPT_LIMIT, keep_lines=False):
    """Qisqa matn. `keep_lines` — qator tashlashlar saqlanadi (ro'yxatsimon xabar uchun)."""
    if keep_lines:
        lines = (' '.join(line.split()) for line in plain_text(text).splitlines())
        text = '\n'.join(line for line in lines if line)
    else:
        text = ' '.join(plain_text(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0] + '…'


def enqueue(kind, obj, title, excerpt, link, image='', keep_lines=False, limit=EXCERPT_LIMIT):
    """Navbatga qo'shadi. O'chirilgan bo'lsa yoki allaqachon bor bo'lsa — jim o'tadi."""
    if not BotSetting.load().auto_post:
        return None

    post, _created = BotPost.objects.get_or_create(
        kind=kind,
        object_id=obj.pk,
        defaults={
            'title': title[:250],
            'excerpt': shorten(excerpt, limit=limit, keep_lines=keep_lines),
            'image_url': image[:400],
            'link': link[:400],
        },
    )
    return post


# --------------------------------------------------------------------------
# Qabul qiluvchilar
# --------------------------------------------------------------------------

@receiver(post_save, dispatch_uid='bot_feed_news')
def news_created(sender, instance, **kwargs):
    if sender.__name__ != 'News' or not instance.is_published:
        return
    enqueue(BotPost.Kind.NEWS, instance, instance.title, instance.excerpt,
            site_link(f'/yangiliklar/{instance.slug}'), file_url(instance.image))


@receiver(post_save, dispatch_uid='bot_feed_announcement')
def announcement_created(sender, instance, **kwargs):
    if sender.__name__ != 'Announcement' or not instance.is_active:
        return
    enqueue(BotPost.Kind.ANNOUNCEMENT, instance, instance.title, instance.body,
            site_link(f'/elonlar/{instance.slug}'), file_url(instance.image))


@receiver(post_save, dispatch_uid='bot_feed_startup')
def startup_approved(sender, instance, **kwargs):
    if sender.__name__ != 'Startup':
        return
    if instance.status != Status.APPROVED or not instance.is_public:
        return
    enqueue(BotPost.Kind.STARTUP, instance, instance.name, instance.about,
            site_link(f'/startaplar/{instance.pk}'), file_url(instance.logo))


@receiver(post_save, dispatch_uid='bot_feed_business')
def business_approved(sender, instance, **kwargs):
    if sender.__name__ != 'BusinessProfile':
        return
    if instance.status != Status.APPROVED or not instance.is_public:
        return
    enqueue(BotPost.Kind.BUSINESS, instance, instance.name, instance.description,
            site_link(f'/tadbirkorlar/{instance.pk}'), file_url(instance.logo))


@receiver(post_save, dispatch_uid='bot_feed_peer')
def peer_published(sender, instance, **kwargs):
    if sender.__name__ != 'Peer':
        return
    if instance.status != Status.APPROVED or not instance.is_published:
        return
    enqueue(BotPost.Kind.PEER, instance,
            f"{instance.full_name} — {instance.get_country_display()}",
            instance.achievements or instance.about,
            site_link(f'/tengdoshlar/{instance.pk}'), file_url(instance.photo))


def money(amount, currency):
    """«500 mln so'm», «1,2 mlrd so'm», «$20 000»."""
    if not amount:
        return ''
    if currency == 'USD':
        return f"${amount:,}".replace(',', ' ')
    for size, word in ((1_000_000_000, 'mlrd'), (1_000_000, 'mln')):
        if amount >= size:
            value = f"{amount / size:.1f}".rstrip('0').rstrip('.').replace('.', ',')
            return f"{value} {word} so'm"
    return f"{amount:,} so'm".replace(',', ' ')


@receiver(post_save, dispatch_uid='bot_feed_funded')
def funded_published(sender, instance, **kwargs):
    """Startap mablag' oldi — hammaga tabrik xabari (bir marta)."""
    if sender.__name__ != 'FundedStartup' or not instance.is_published:
        return
    amount = money(instance.amount, instance.currency)
    title = (f"{instance.name} {amount} mablag' oldi! 🎉" if amount
             else f"{instance.name} mablag' oldi! 🎉")
    lines = []
    if instance.funder:
        lines.append(f"🏦 {instance.funder}" + (f" tomonidan {amount} ajratildi." if amount else ""))
    if instance.founder:
        lines.append(f"👤 Asoschi: {instance.founder}")
    lines.append("Keyingi navbat — sizniki! 🚀")
    if instance.about:
        lines.append(instance.about)
    enqueue(BotPost.Kind.FUNDED, instance, title, "\n".join(lines),
            site_link(f'/?mablag={instance.pk}'), file_url(instance.image),
            keep_lines=True, limit=600)


@receiver(post_save, dispatch_uid='bot_feed_problem')
def problem_published(sender, instance, **kwargs):
    """Faqat tashkilotlarning muammolari — yoshlarning tashabbuslari botga bormaydi."""
    if sender.__name__ != 'Problem':
        return
    if instance.status != Status.APPROVED or not instance.is_published:
        return
    organization = instance.organization
    title = f"{organization.name}: {instance.question or instance.get_category_display()}"
    enqueue(BotPost.Kind.PROBLEM, instance, title, instance.description,
            site_link(f'/tashabbuslar/muammolar/{instance.pk}'))


def _poll_ready(poll):
    """So'rovnoma botga faqat ovoz berish ochiq va kamida 2 nomzod bo'lganda chiqadi —
    aks holda odam havolani ochib, bo'sh sahifa ko'radi."""
    # Tasdiqlanmagan arizalar sanalmaydi — ular saytda ko'rinmaydi
    return poll.is_open and poll.options.filter(status='approved').count() >= 2


def enqueue_poll(poll):
    """Tayyor bo'lsa navbatga qo'shadi (bir so'rovnoma — bir marta).

    Panel nomzodlarni saqlab bo'lgach shuni bir marta chaqiradi; har bir
    nomzod saqlanganda emas — aks holda 300 nomzodli so'rovnoma yuzlab
    ortiqcha so'rov bilan saqlanardi.
    """
    if not _poll_ready(poll):
        return None
    return enqueue(BotPost.Kind.POLL, poll, poll.title,
                   poll.description or "Ovoz bering — reyting har bir ovoz bilan yangilanadi.",
                   site_link(f'/sorovnomalar/{poll.slug}'), file_url(poll.image))


@receiver(post_save, dispatch_uid='bot_feed_poll')
def poll_published(sender, instance, **kwargs):
    """Ko'rinishi yoqilgan yoki tahrirlangan so'rovnoma (nomzodlari allaqachon bor)."""
    if sender.__name__ != 'Poll':
        return
    enqueue_poll(instance)
