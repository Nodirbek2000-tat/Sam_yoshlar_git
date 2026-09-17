"""Saytga yangi narsa qo'shilsa — botga yuborish navbatiga qo'shadi.

Yangilik, e'lon, startap, tadbirkor yoki chet eldagi tengdosh chiqqanda
shu yerdagi qabul qiluvchilar ishlaydi. Panelda «Botga yuborish» o'chiq
bo'lsa — navbatga hech narsa tushmaydi.

Navbatni botning o'zi olib, hamma foydalanuvchiga yuboradi: rasm, matn
boshlanishi va «Davomini o'qish» tugmasi.
"""

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


def shorten(text, limit=EXCERPT_LIMIT):
    text = ' '.join((text or '').split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0] + '…'


def enqueue(kind, obj, title, excerpt, link, image=''):
    """Navbatga qo'shadi. O'chirilgan bo'lsa yoki allaqachon bor bo'lsa — jim o'tadi."""
    if not BotSetting.load().auto_post:
        return None

    post, _created = BotPost.objects.get_or_create(
        kind=kind,
        object_id=obj.pk,
        defaults={
            'title': title[:250],
            'excerpt': shorten(excerpt),
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
            site_link(f'/elonlar/{instance.slug}'))


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
