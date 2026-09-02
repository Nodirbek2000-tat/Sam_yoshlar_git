"""Mavjud hisobga Telegram raqamini bog'lash.

Telegram orqali kirgan odam avtomatik admin BO'LMAYDI — oddiy foydalanuvchi bo'ladi.
Agar o'z hisobingizga (masalan superuser) Telegram orqali kirmoqchi bo'lsangiz,
shu buyruq bilan raqamni bog'lab qo'ying: bot o'sha raqamni yuborganda
yangi hisob ochilmaydi, mavjud hisobingizga kiradi.

    python manage.py link_telegram nodirbek.shukurov09q@gmail.com --phone "+998500056821"
    python manage.py link_telegram 1 --phone "+998500056821"
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Hisobga telefon raqamini bog'laydi (Telegram orqali kirish uchun)."

    def add_arguments(self, parser):
        parser.add_argument('user', help="Foydalanuvchi email yoki ID raqami")
        parser.add_argument('--phone', required=True,
                            help="Telegramdagi telefon raqami, masalan +998500056821")
        parser.add_argument('--telegram-id', type=int, default=None,
                            help="Telegram ID (ixtiyoriy — bot o'zi to'ldiradi)")

    def handle(self, *args, **options):
        identifier = options['user']
        phone = self._normalize(options['phone'])

        if identifier.isdigit():
            user = User.objects.filter(pk=int(identifier)).first()
        else:
            user = User.objects.filter(email__iexact=identifier).first()

        if user is None:
            raise CommandError(f"Foydalanuvchi topilmadi: {identifier}")

        clash = User.objects.filter(phone=phone).exclude(pk=user.pk).first()
        if clash:
            raise CommandError(
                f"Bu raqam boshqa hisobga biriktirilgan: #{clash.pk} {clash.full_name}. "
                f"Avval o'shani o'chiring yoki raqamini o'zgartiring."
            )

        user.phone = phone
        fields = ['phone']

        if options['telegram_id']:
            user.telegram_id = options['telegram_id']
            fields.append('telegram_id')

        user.save(update_fields=fields)

        self.stdout.write(self.style.SUCCESS(
            f"Bog'landi: #{user.pk} {user.full_name} -> {phone}"
        ))
        self.stdout.write(
            f"  superuser={user.is_superuser}  staff={user.is_staff}  rol={user.role}"
        )
        self.stdout.write(
            "\nEndi botga shu raqamni yuborsangiz, aynan shu hisobga kirasiz."
        )

    @staticmethod
    def _normalize(phone):
        """Bo'shliq, qavs va tirelarni olib tashlaydi: +998 50 005-68-21 -> +998500056821"""
        cleaned = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
        if cleaned and not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        return cleaned
