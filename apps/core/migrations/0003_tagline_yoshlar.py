from django.db import migrations, models

OLD = ("O'zbekiston yosh tadbirkorlarini birlashtiruvchi, qo'llab-quvvatlovchi va "
       "rivojlantirishga xizmat qiluvchi yagona axborot platformasi.")
NEW = ("Yoshlarni birlashtiruvchi, qo'llab-quvvatlovchi va "
       "rivojlantirishga xizmat qiluvchi yagona axborot platformasi.")


def to_new(apps, schema_editor):
    """Bazada eski matn tursa, yangisiga almashtiramiz.

    Admin qo'lda boshqa matn yozgan bo'lsa — tegmaymiz.
    """
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(tagline=OLD).update(tagline=NEW)


def to_old(apps, schema_editor):
    SiteSetting = apps.get_model('core', 'SiteSetting')
    SiteSetting.objects.filter(tagline=NEW).update(tagline=OLD)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_leader_task_sitesetting_charter_file_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesetting',
            name='tagline',
            field=models.TextField(default=NEW, verbose_name='Qisqa tavsif'),
        ),
        migrations.RunPython(to_new, to_old),
    ]
