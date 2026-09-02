from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrPhoneBackend(ModelBackend):
    """Email yoki telefon raqami bilan kirish imkonini beradi."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        identifier = username or kwargs.get('email')
        if not identifier or not password:
            return None
        try:
            user = User.objects.get(
                Q(email__iexact=identifier.strip()) | Q(phone=identifier.strip())
            )
        except User.DoesNotExist:
            User().set_password(password)  # timing attack'dan himoya
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=identifier.strip()).first()
            if user is None:
                return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
