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


class Status(models.TextChoices):
    """Ariza / murojaat / taklif uchun umumiy holat."""

    PENDING = 'pending', "Kutilmoqda"
    REVIEW = 'review', "Ko'rib chiqilmoqda"
    APPROVED = 'approved', "Tasdiqlangan"
    REJECTED = 'rejected', "Rad etilgan"
    DONE = 'done', "Bajarilgan"
