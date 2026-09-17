from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self):
        # Yangi yangilik/e'lon/startap qo'shilganda botga yuborish navbatiga tushadi
        from . import bot_feed  # noqa: F401
