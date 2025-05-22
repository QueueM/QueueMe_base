from django.apps import AppConfig


class UtilsConfig(AppConfig):
    name = "utils"
    verbose_name = "QueueMe Utilities"

    def ready(self):
        """
        Import signal handlers when the app is ready
        """
        # Import any signals or other initialization code here
