from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class PhoneNumberBackend(ModelBackend):
    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        from apps.authapp.models import User

        if phone_number is None:
            phone_number = kwargs.get("username")

        if phone_number is None or password is None:
            return None

        try:
            # Clean phone number format if needed
            if phone_number.startswith("+"):
                phone_number = phone_number[1:]
            elif phone_number.startswith("0"):
                phone_number = "966" + phone_number[1:]

            user = User.objects.get(
                Q(phone_number=phone_number)
                | Q(phone_number="966" + phone_number)
                | Q(phone_number="+" + phone_number)
                | Q(phone_number="+966" + phone_number)
            )

            if user.check_password(password):
                return user

        except User.DoesNotExist:
            # Run the default password hasher once to reduce timing
            # attack vector (see comments for more details)
            User().set_password(password)

        return None
