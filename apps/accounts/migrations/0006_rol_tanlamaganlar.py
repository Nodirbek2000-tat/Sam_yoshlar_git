"""Telegram orqali kelgan, lekin rolni tanlamay «tadbirkor» bo'lib qolganlar.

Bot yangi hisobni `is_verified=True` bilan ochgani uchun sayt rol savolini
o'tkazib yuborib, ularni to'g'ri biznes anketasiga yuborardi. Biznes
profili yo'q bunday hisoblar rol tanlash qadamiga qaytariladi.
"""

from django.db import migrations


def reset_role_step(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    BusinessProfile = apps.get_model('business', 'BusinessProfile')

    with_business = BusinessProfile.objects.values_list('user_id', flat=True)
    (User.objects
     .filter(role='entrepreneur', is_verified=True, is_superuser=False, is_staff=False,
             email__endswith='@telegram.local')
     .exclude(pk__in=with_business)
     .update(is_verified=False))


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_yosh_va_talim'),
        ('business', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(reset_role_step, migrations.RunPython.noop),
    ]
