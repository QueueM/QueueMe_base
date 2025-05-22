import os

from colorama import Fore, Style, init
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check Moyasar payment gateway configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test",
            action="store_true",
            help="Test connection to Moyasar API",
        )

    def handle(self, *args, **options):
        # Initialize colorama for cross-platform colored terminal output
        init()

        self.stdout.write(self.style.HTTP_INFO("Checking Moyasar configuration..."))

        # Check basic settings
        self.stdout.write("\nLegacy settings:")
        if hasattr(settings, "MOYASAR_API_KEY") and settings.MOYASAR_API_KEY:
            self.stdout.write(f"  MOYASAR_API_KEY: {Fore.GREEN}Set{Style.RESET_ALL}")
        else:
            self.stdout.write(f"  MOYASAR_API_KEY: {Fore.RED}Missing{Style.RESET_ALL}")

        if (
            hasattr(settings, "MOYASAR_WEBHOOK_SECRET")
            and settings.MOYASAR_WEBHOOK_SECRET
        ):
            self.stdout.write(
                f"  MOYASAR_WEBHOOK_SECRET: {Fore.GREEN}Set{Style.RESET_ALL}"
            )
        else:
            self.stdout.write(
                f"  MOYASAR_WEBHOOK_SECRET: {Fore.RED}Missing{Style.RESET_ALL}"
            )

        # Check wallet configurations
        self.check_wallet_config("subscription", "MOYASAR_SUB", "MOYASAR_SUB")
        self.check_wallet_config("ads", "MOYASAR_ADS", "MOYASAR_ADS")
        self.check_wallet_config("merchant", "MOYASAR_MER", "MOYASAR_MER")

        # Test connection if requested
        if options["test"]:
            self.test_moyasar_connection()

    def check_wallet_config(self, wallet_name, settings_attr, env_prefix):
        """Check configuration for a specific wallet"""
        self.stdout.write(f"\n{wallet_name.upper()} wallet configuration:")

        # Check settings object first
        wallet_config = (
            getattr(settings, settings_attr, {})
            if hasattr(settings, settings_attr)
            else {}
        )

        if wallet_config:
            self.stdout.write(f"  Using configuration from settings.{settings_attr}")
            self.check_wallet_keys(wallet_config)
        else:
            self.stdout.write(f"  No configuration found in settings.{settings_attr}")
            self.stdout.write("  Checking environment variables:")

            # Check environment variables
            env_config = {
                "public_key": os.environ.get(f"{env_prefix}_PUBLIC", ""),
                "secret_key": os.environ.get(f"{env_prefix}_SECRET", ""),
                "wallet_id": os.environ.get(f"{env_prefix}_WALLET_ID", ""),
                "callback_url": os.environ.get(f"{env_prefix}_CALLBACK_URL", ""),
            }

            if env_prefix == "MOYASAR_SUB":
                env_config["callback_url_complete"] = os.environ.get(
                    f"{env_prefix}_CALLBACK_URL_COMPLETE", ""
                )

            self.check_wallet_keys(env_config, from_env=True, prefix=env_prefix)

    def check_wallet_keys(self, config, from_env=False, prefix=None):
        """Check the required keys in a wallet configuration"""
        required_keys = ["public_key", "secret_key", "wallet_id", "callback_url"]
        if "callback_url_complete" in config:
            required_keys.append("callback_url_complete")

        all_present = True

        for key in required_keys:
            env_key = f"{prefix}_{key.upper()}" if from_env and prefix else None
            value = config.get(key, "")

            if value:
                self.stdout.write(
                    f"  {key}: {Fore.GREEN}Set{Style.RESET_ALL}"
                    + (f" (from {env_key})" if env_key else "")
                )
            else:
                self.stdout.write(
                    f"  {key}: {Fore.RED}Missing{Style.RESET_ALL}"
                    + (f" (from {env_key})" if env_key else "")
                )
                all_present = False

        if all_present:
            self.stdout.write(
                f"  {Fore.GREEN}✓ All required configuration present{Style.RESET_ALL}"
            )
        else:
            self.stdout.write(
                f"  {Fore.RED}✗ Missing required configuration{Style.RESET_ALL}"
            )

    def test_moyasar_connection(self):
        """Test connection to Moyasar API"""


        self.stdout.write("\nTesting connection to Moyasar API...")

        # Check subscription wallet
        self.test_wallet_connection("subscription")

        # Check ads wallet
        self.test_wallet_connection("ad")

        # Check merchant wallet
        self.test_wallet_connection("booking")

    def test_wallet_connection(self, transaction_type):
        """Test connection for a specific wallet"""
        import requests

        from apps.payment.services.moyasar_service import MoyasarService

        wallet_config = MoyasarService.get_wallet_config(transaction_type)
        auth_header = MoyasarService.get_authorization_header(transaction_type)

        self.stdout.write(f"\nTesting {transaction_type} wallet connection:")

        if not wallet_config.get("secret_key"):
            self.stdout.write(
                f"  {Fore.RED}✗ No secret key available for this wallet{Style.RESET_ALL}"
            )
            return

        try:
            # Use a valid Moyasar API endpoint
            response = requests.get(
                "https://api.moyasar.com/v1/payment_methods",
                headers={"Authorization": auth_header},
                timeout=5,
            )

            if response.status_code == 200:
                self.stdout.write(
                    f"  {Fore.GREEN}✓ Connection successful{Style.RESET_ALL}"
                )
                self.stdout.write(f"  Response: {response.json()}")
            else:
                self.stdout.write(
                    f"  {Fore.RED}✗ Connection failed with status code {response.status_code}{Style.RESET_ALL}"
                )
                self.stdout.write(f"  Response: {response.text}")
        except Exception as e:
            self.stdout.write(
                f"  {Fore.RED}✗ Connection error: {str(e)}{Style.RESET_ALL}"
            )
