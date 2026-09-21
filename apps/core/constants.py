"""Loyiha bo'ylab ishlatiladigan umumiy ro'yxatlar."""

from django.db import models


class Region(models.TextChoices):
    TOSHKENT_SHAHRI = 'toshkent_shahri', "Toshkent shahri"
    TOSHKENT = 'toshkent', "Toshkent viloyati"
    SAMARQAND = 'samarqand', "Samarqand viloyati"
    BUXORO = 'buxoro', "Buxoro viloyati"
    NAVOIY = 'navoiy', "Navoiy viloyati"
    QASHQADARYO = 'qashqadaryo', "Qashqadaryo viloyati"
    SURXONDARYO = 'surxondaryo', "Surxondaryo viloyati"
    FARGONA = 'fargona', "Farg'ona viloyati"
    ANDIJON = 'andijon', "Andijon viloyati"
    NAMANGAN = 'namangan', "Namangan viloyati"
    XORAZM = 'xorazm', "Xorazm viloyati"
    SIRDARYO = 'sirdaryo', "Sirdaryo viloyati"
    JIZZAX = 'jizzax', "Jizzax viloyati"
    QORAQALPOGISTON = 'qoraqalpogiston', "Qoraqalpog'iston Respublikasi"


class SamarqandDistrict(models.TextChoices):
    """Samarqand viloyatining tuman va shaharlari.

    Botda ro'yxatdan o'tayotgan odamdan shu ro'yxatdan bittasi so'raladi.
    """

    SAMARQAND_SHAHRI = 'samarqand_shahri', "Samarqand shahri"
    KATTAQORGON_SHAHRI = 'kattaqorgon_shahri', "Kattaqo'rg'on shahri"
    BULUNGUR = 'bulungur', "Bulung'ur tumani"
    JOMBOY = 'jomboy', "Jomboy tumani"
    ISHTIXON = 'ishtixon', "Ishtixon tumani"
    KATTAQORGON = 'kattaqorgon', "Kattaqo'rg'on tumani"
    QOSHRABOT = 'qoshrabot', "Qo'shrabot tumani"
    NARPAY = 'narpay', "Narpay tumani"
    NUROBOD = 'nurobod', "Nurobod tumani"
    OQDARYO = 'oqdaryo', "Oqdaryo tumani"
    PASTDARGOM = 'pastdargom', "Pastdarg'om tumani"
    PAXTACHI = 'paxtachi', "Paxtachi tumani"
    PAYARIQ = 'payariq', "Payariq tumani"
    SAMARQAND_TUMANI = 'samarqand_tumani', "Samarqand tumani"
    TOYLOQ = 'toyloq', "Toyloq tumani"
    URGUT = 'urgut', "Urgut tumani"


def district_options():
    """Bot va API uchun ro'yxat: [{'value': ..., 'label': ...}, ...]."""
    return [{'value': value, 'label': label} for value, label in SamarqandDistrict.choices]


def _normalize(text):
    return (str(text or '').strip().lower()
            .replace('’', "'").replace('`', "'").replace('ʻ', "'"))


def _short(label):
    """«Urgut tumani» -> «urgut». Takrorlanadigan qisqa nomlar hisobga olinmaydi."""
    return _normalize(label).replace(' tumani', '').replace(' shahri', '')


def _district_index():
    index = {}
    seen_short = {}

    for value, label in SamarqandDistrict.choices:
        index[value] = label
        index[_normalize(label)] = label
        seen_short.setdefault(_short(label), []).append(label)

    # Qisqa nom faqat bitta tumanga tegishli bo'lsa qabul qilinadi
    # («samarqand» ham shahar, ham tuman — shuning uchun tushib qoladi)
    for short, labels in seen_short.items():
        if len(labels) == 1 and short not in index:
            index[short] = labels[0]

    return index


def district_label(raw):
    """Kod yoki nomni rasmiy nomga aylantiradi. Topilmasa — bo'sh satr."""
    return _district_index().get(_normalize(raw), '')


class Status(models.TextChoices):
    """Ariza / murojaat / taklif uchun umumiy holat."""

    PENDING = 'pending', "Kutilmoqda"
    REVIEW = 'review', "Ko'rib chiqilmoqda"
    APPROVED = 'approved', "Tasdiqlangan"
    REJECTED = 'rejected', "Rad etilgan"
    DONE = 'done', "Bajarilgan"
