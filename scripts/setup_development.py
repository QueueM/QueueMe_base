#!/usr/bin/env python
# =============================================================================
# Queue Me Development Environment Setup
# Sophisticated developer onboarding script with automated setup and validation
# =============================================================================

import argparse
import getpass
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("setup_development.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Set base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SetupDevelopment:
    def __init__(self, args):
        self.args = args
        self.os_type = platform.system()
        self.python_cmd = self._get_python_cmd()
        self.env_file = os.path.join(BASE_DIR, ".env")
        self.venv_dir = os.path.join(BASE_DIR, "venv")
        self.requirements_file = os.path.join(BASE_DIR, "requirements.txt")
        self.config = self._load_config()

        # Setup state tracking
        self.setup_state = {
            "prerequisites_checked": False,
            "virtualenv_created": False,
            "dependencies_installed": False,
            "env_file_created": False,
            "migrations_applied": False,
            "initial_data_loaded": False,
            "superuser_created": False,
            "development_server_tested": False,
            "celery_setup_completed": False,
            "completed_at": None,
            "username": None,
        }

        # Load previous state if exists
        self._load_state()

    def _get_python_cmd(self):
        """Get correct Python command based on OS"""
        if self.os_type == "Windows":
            return "python"
        else:
            return "python3"

    def _load_config(self):
        """Load configuration from config file"""
        config_path = os.path.join(
            BASE_DIR, "config", "development", "setup_config.json"
        )
        default_config = {
            "required_packages": ["git", "pip", "virtualenv"],
            "recommended_python_version": "3.9",
            "database": {
                "engine": "sqlite3",
                "name": "db.sqlite3",
                "user": "",
                "password": "",
                "host": "",
                "port": "",
            },
            "redis": {"host": "localhost", "port": 6379},
            "initial_superuser": {
                "phone_number": "+966555555555",
                "password": "admin123",
            },
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
            else:
                logger.warning(
                    f"Config file not found at {config_path}. Using default configuration."
                )
                return default_config
        except json.JSONDecodeError:
            logger.error("Error parsing config file. Using default configuration.")
            return default_config

    def _load_state(self):
        """Load previous setup state if exists"""
        state_path = os.path.join(BASE_DIR, ".setup_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    saved_state = json.load(f)
                    self.setup_state.update(saved_state)

                    if saved_state.get("completed_at"):
                        logger.info(
                            f"Previous setup was completed on {saved_state['completed_at']} by {saved_state.get('username', 'unknown')}"
                        )
            except json.JSONDecodeError:
                logger.warning("Could not parse previous setup state. Starting fresh.")

    def _save_state(self):
        """Save current setup state"""
        state_path = os.path.join(BASE_DIR, ".setup_state.json")
        with open(state_path, "w") as f:
            json.dump(self.setup_state, f, indent=2)

    def _run_command(self, command, cwd=None, env=None):
        """Run a shell command and return its output"""
        try:
            output = subprocess.check_output(
                command,
                stderr=subprocess.STDOUT,
                shell=True,
                cwd=cwd or BASE_DIR,
                env=env,
                universal_newlines=True,
            )
            return True, output
        except subprocess.CalledProcessError as e:
            return False, e.output

    def _activate_venv(self):
        """Return environment with activated virtualenv"""
        env = os.environ.copy()

        if self.os_type == "Windows":
            env["PATH"] = (
                os.path.join(self.venv_dir, "Scripts") + os.pathsep + env["PATH"]
            )
            python_path = os.path.join(self.venv_dir, "Scripts", "python.exe")
        else:
            env["PATH"] = os.path.join(self.venv_dir, "bin") + os.pathsep + env["PATH"]
            python_path = os.path.join(self.venv_dir, "bin", "python")

        env["VIRTUAL_ENV"] = self.venv_dir
        return env, python_path

    def check_prerequisites(self):
        """Check system prerequisites"""
        if self.setup_state["prerequisites_checked"] and not self.args.force:
            logger.info("Prerequisites already checked. Use --force to recheck.")
            return True

        logger.info("Checking prerequisites...")

        # Check Python version
        python_version = platform.python_version()
        recommended_version = self.config["recommended_python_version"]

        logger.info(f"Found Python version: {python_version}")
        if not python_version.startswith(recommended_version):
            logger.warning(
                f"Recommended Python version is {recommended_version}, but found {python_version}"
            )
            if self.args.strict:
                return False

        # Check required packages
        all_packages_found = True
        for package in self.config["required_packages"]:
            success, output = self._run_command(
                f"which {package}" if self.os_type != "Windows" else f"where {package}"
            )

            if success:
                logger.info(f"Found required package: {package}")
            else:
                logger.error(f"Missing required package: {package}")
                all_packages_found = False

        if not all_packages_found and self.args.strict:
            return False

        # Check Git
        success, git_version = self._run_command("git --version")
        if success:
            logger.info(f"Git is available: {git_version.strip()}")
        else:
            logger.error("Git not found. Please install Git.")
            if self.args.strict:
                return False

        # Check database tools
        if self.config["database"]["engine"] == "postgresql":
            success, pg_version = self._run_command("pg_config --version")
            if success:
                logger.info(f"PostgreSQL tools are available: {pg_version.strip()}")
            else:
                logger.warning(
                    "PostgreSQL tools not found. You may need to install them for PostgreSQL integration."
                )

        # Check Redis (if needed for Celery)
        success, redis_version = self._run_command("redis-cli --version")
        if success:
            logger.info(f"Redis CLI is available: {redis_version.strip()}")
        else:
            logger.warning(
                "Redis CLI not found. You will need Redis for Celery background tasks."
            )

        self.setup_state["prerequisites_checked"] = True
        self._save_state()
        return True

    def create_virtual_environment(self):
        """Create a virtual environment"""
        if (
            self.setup_state["virtualenv_created"]
            and os.path.exists(self.venv_dir)
            and not self.args.force
        ):
            logger.info("Virtual environment already exists. Use --force to recreate.")
            return True

        logger.info("Creating virtual environment...")

        if os.path.exists(self.venv_dir) and self.args.force:
            logger.info("Removing existing virtual environment...")
            shutil.rmtree(self.venv_dir)

        command = f"{self.python_cmd} -m venv {self.venv_dir}"
        success, output = self._run_command(command)

        if success:
            logger.info("Virtual environment created successfully")
            self.setup_state["virtualenv_created"] = True
            self._save_state()
            return True
        else:
            logger.error(f"Failed to create virtual environment: {output}")
            return False

    def install_dependencies(self):
        """Install dependencies from requirements file"""
        if self.setup_state["dependencies_installed"] and not self.args.force:
            logger.info("Dependencies already installed. Use --force to reinstall.")
            return True

        logger.info("Installing dependencies...")

        # Get virtualenv environment variables
        env, python_path = self._activate_venv()

        # Check if requirements directory exists instead of file
        requirements_dir = os.path.join(BASE_DIR, "requirements")
        if os.path.isdir(requirements_dir):
            # Install base requirements first, then development
            base_req = os.path.join(requirements_dir, "base.txt")
            dev_req = os.path.join(requirements_dir, "development.txt")

            if os.path.exists(base_req):
                logger.info("Installing base requirements...")
                success, output = self._run_command(
                    f'"{python_path}" -m pip install -r {base_req}', env=env
                )
                if not success:
                    logger.error(f"Failed to install base requirements: {output}")
                    return False

            if os.path.exists(dev_req):
                logger.info("Installing development requirements...")
                success, output = self._run_command(
                    f'"{python_path}" -m pip install -r {dev_req}', env=env
                )
                if not success:
                    logger.error(
                        f"Failed to install development requirements: {output}"
                    )
                    return False
        else:
            # Use main requirements file
            if not os.path.exists(self.requirements_file):
                logger.error(f"Requirements file not found at {self.requirements_file}")
                return False

            logger.info("Installing requirements...")
            success, output = self._run_command(
                f'"{python_path}" -m pip install -r {self.requirements_file}', env=env
            )

            if not success:
                logger.error(f"Failed to install dependencies: {output}")
                return False

        logger.info("Dependencies installed successfully")
        self.setup_state["dependencies_installed"] = True
        self._save_state()
        return True

    def create_env_file(self):
        """Create .env file from template or user input"""
        if (
            self.setup_state["env_file_created"]
            and os.path.exists(self.env_file)
            and not self.args.force
        ):
            logger.info(".env file already exists. Use --force to recreate.")
            return True

        logger.info("Creating .env file...")

        # Check for .env.example
        env_example = os.path.join(BASE_DIR, ".env.example")
        if os.path.exists(env_example):
            # Copy from example
            with open(env_example, "r") as src, open(self.env_file, "w") as dest:
                content = src.read()

                # Replace placeholders with real values
                replacements = {
                    "DEBUG=False": "DEBUG=True",
                    "ALLOWED_HOSTS=localhost,127.0.0.1,queueme.net,*.queueme.net": "ALLOWED_HOSTS=localhost,127.0.0.1",
                    "POSTGRES_HOST=db": f"POSTGRES_HOST={self.config['database'].get('host', 'localhost')}",
                    "POSTGRES_DB=queueme": f"POSTGRES_DB={self.config['database'].get('name', 'queueme')}",
                    "POSTGRES_USER=queueme": f"POSTGRES_USER={self.config['database'].get('user', 'queueme')}",
                    "POSTGRES_PASSWORD=queueme": f"POSTGRES_PASSWORD={self.config['database'].get('password', 'queueme')}",
                    "REDIS_HOST=redis": f"REDIS_HOST={self.config['redis'].get('host', 'localhost')}",
                    "REDIS_PORT=6379": f"REDIS_PORT={self.config['redis'].get('port', 6379)}",
                    "DJANGO_SUPERUSER_PHONE=9966889977": f"DJANGO_SUPERUSER_PHONE={self.config['initial_superuser'].get('phone_number', '+966555555555').replace('+', '')}",
                    "DJANGO_SUPERUSER_PASSWORD=admin123": f"DJANGO_SUPERUSER_PASSWORD={self.config['initial_superuser'].get('password', 'admin123')}",
                }

                for old, new in replacements.items():
                    content = content.replace(old, new)

                dest.write(content)

            logger.info(f".env file created from template at {self.env_file}")
        else:
            # Create minimal .env file
            with open(self.env_file, "w") as f:
                f.write("DEBUG=True\n")
                f.write(
                    f"SECRET_KEY=development-secret-key-{datetime.now().strftime('%Y%m%d')}\n"
                )
                f.write("ALLOWED_HOSTS=localhost,127.0.0.1\n")

                f.write("\n# Database settings\n")
                f.write(
                    f"POSTGRES_HOST={self.config['database'].get('host', 'localhost')}\n"
                )
                f.write(f"POSTGRES_PORT={self.config['database'].get('port', 5432)}\n")
                f.write(
                    f"POSTGRES_DB={self.config['database'].get('name', 'queueme')}\n"
                )
                f.write(
                    f"POSTGRES_USER={self.config['database'].get('user', 'queueme')}\n"
                )
                f.write(
                    f"POSTGRES_PASSWORD={self.config['database'].get('password', 'queueme')}\n"
                )

                f.write("\n# Redis settings\n")
                f.write(f"REDIS_HOST={self.config['redis'].get('host', 'localhost')}\n")
                f.write(f"REDIS_PORT={self.config['redis'].get('port', 6379)}\n")

                f.write("\n# Superuser settings\n")
                f.write(
                    f"DJANGO_SUPERUSER_PHONE={self.config['initial_superuser'].get('phone_number', '+966555555555').replace('+', '')}\n"
                )
                f.write(
                    f"DJANGO_SUPERUSER_PASSWORD={self.config['initial_superuser'].get('password', 'admin123')}\n"
                )

            logger.info(f"Minimal .env file created at {self.env_file}")

        self.setup_state["env_file_created"] = True
        self._save_state()
        return True

    def apply_migrations(self):
        """Apply database migrations"""
        if self.setup_state["migrations_applied"] and not self.args.force:
            logger.info("Migrations already applied. Use --force to reapply.")
            return True

        logger.info("Applying migrations...")

        # Get virtualenv environment variables
        env, python_path = self._activate_venv()

        # Apply migrations
        success, output = self._run_command(
            f'"{python_path}" manage.py migrate', env=env
        )

        if success:
            logger.info("Migrations applied successfully")
            self.setup_state["migrations_applied"] = True
            self._save_state()
            return True
        else:
            logger.error(f"Failed to apply migrations: {output}")
            return False

    def load_initial_data(self):
        """Load initial data"""
        if self.setup_state["initial_data_loaded"] and not self.args.force:
            logger.info("Initial data already loaded. Use --force to reload.")
            return True

        logger.info("Loading initial data...")

        # Get virtualenv environment variables
        env, python_path = self._activate_venv()

        # Check if fixture files exist
        fixtures_dir = os.path.join(BASE_DIR, "fixtures")
        fixtures_exist = os.path.isdir(fixtures_dir) and any(
            f.endswith(".json") for f in os.listdir(fixtures_dir)
        )

        if fixtures_exist:
            # Load all fixture files
            for fixture_file in sorted(os.listdir(fixtures_dir)):
                if fixture_file.endswith(".json"):
                    fixture_path = os.path.join("fixtures", fixture_file)
                    logger.info(f"Loading fixture: {fixture_file}")
                    success, output = self._run_command(
                        f'"{python_path}" manage.py loaddata {fixture_path}', env=env
                    )

                    if not success:
                        logger.error(f"Failed to load fixture {fixture_file}: {output}")
                        return False
        else:
            # Use seed_data.py script if available
            seed_script = os.path.join(BASE_DIR, "scripts", "seed_data.py")
            if os.path.exists(seed_script):
                logger.info("Running seed data script...")
                success, output = self._run_command(
                    f'"{python_path}" {seed_script} --scale 0.1', env=env
                )

                if not success:
                    logger.error(f"Failed to run seed data script: {output}")
                    if self.args.strict:
                        return False
            else:
                logger.warning(
                    "No fixtures or seed script found. Skipping initial data loading."
                )

        logger.info("Initial data loaded successfully")
        self.setup_state["initial_data_loaded"] = True
        self._save_state()
        return True

    def create_superuser(self):
        """Create superuser account"""
        if self.setup_state["superuser_created"] and not self.args.force:
            logger.info("Superuser already created. Use --force to recreate.")
            return True

        logger.info("Creating superuser account...")

        # Get virtualenv environment variables
        env, python_path = self._activate_venv()

        # Create superuser with environment variables from .env file
        phone_number = (
            self.config["initial_superuser"]
            .get("phone_number", "+966555555555")
            .replace("+", "")
        )
        password = self.config["initial_superuser"].get("password", "admin123")

        # First check if superuser exists
        check_cmd = f""""{python_path}" -c "import os; import django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.development'); django.setup(); from apps.authapp.models import User; print(User.objects.filter(phone_number='{phone_number}', is_superuser=True).exists())" """
        success, output = self._run_command(check_cmd, env=env)

        if success and "True" in output:
            logger.info(f"Superuser with phone number {phone_number} already exists.")
            self.setup_state["superuser_created"] = True
            self._save_state()
            return True

        # Create superuser
        create_cmd = f""""{python_path}" -c "import os; import django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.development'); django.setup(); from apps.authapp.models import User; User.objects.create_superuser(phone_number='{phone_number}', password='{password}')" """
        success, output = self._run_command(create_cmd, env=env)

        if success:
            logger.info(
                f"Superuser created with phone: {phone_number} and password: {password}"
            )
            self.setup_state["superuser_created"] = True
            self._save_state()
            return True
        else:
            logger.error(f"Failed to create superuser: {output}")
            return False

    def test_development_server(self):
        """Test running development server"""
        if self.setup_state["development_server_tested"] and not self.args.force:
            logger.info("Development server already tested. Use --force to retest.")
            return True

        logger.info("Testing development server...")

        # Get virtualenv environment variables
        env, python_path = self._activate_venv()

        # Start server in a separate process and terminate after a few seconds
        import signal
        import subprocess
        import time

        server_process = subprocess.Popen(
            f'"{python_path}" manage.py runserver --noreload 8000',
            shell=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        try:
            # Wait for server to start
            time.sleep(3)

            # Check if server is running
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(("localhost", 8000))
            is_running = result == 0
            sock.close()

            if is_running:
                logger.info("Development server started successfully")
                self.setup_state["development_server_tested"] = True
                self._save_state()
                return True
            else:
                logger.error("Failed to start development server")
                return False

        finally:
            # Terminate server
            if self.os_type == "Windows":
                server_process.terminate()
            else:
                os.kill(server_process.pid, signal.SIGTERM)
            server_process.wait()

    def setup_celery(self):
        """Setup Celery for background tasks"""
        if self.setup_state["celery_setup_completed"] and not self.args.force:
            logger.info("Celery setup already completed. Use --force to redo setup.")
            return True

        logger.info("Setting up Celery...")

        # Get virtualenv environment variables
        env, python_path = self._activate_venv()

        # Check if Redis is available
        success, output = self._run_command("redis-cli ping", env=env)
        if not success or "PONG" not in output:
            logger.warning(
                "Redis does not appear to be running. Celery requires Redis."
            )
            # apps/scripts/setup_development.py (continued)

        # Check if celery.py exists
        celery_file = os.path.join(BASE_DIR, "queueme", "celery.py")
        if not os.path.exists(celery_file):
            logger.warning(f"Celery configuration file not found at {celery_file}")
            if self.args.strict:
                return False

        # Test Celery configuration
        success, output = self._run_command(
            f'"{python_path}" -m celery --version', env=env
        )
        if not success:
            logger.error(f"Celery is not installed or configured properly: {output}")
            return False

        logger.info(f"Celery version: {output.strip()}")

        # Test Celery with app
        test_cmd = f"\"{python_path}\" -c \"import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'queueme.settings.development'); from queueme.celery import app; print('Celery app configured:', app)\""
        success, output = self._run_command(test_cmd, env=env)

        if success and "Celery app configured" in output:
            logger.info("Celery configuration is valid")
            self.setup_state["celery_setup_completed"] = True
            self._save_state()
            return True
        else:
            logger.error(f"Celery configuration test failed: {output}")
            return False

    def setup_complete(self):
        """Mark setup as complete and display summary"""
        # Get username for completion tracking
        try:
            username = getpass.getuser()
        except BaseException:
            username = "unknown"

        self.setup_state["username"] = username
        self.setup_state["completed_at"] = datetime.now().isoformat()
        self._save_state()

        logger.info("")
        logger.info("=" * 80)
        logger.info("SETUP COMPLETE!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Queue Me development environment has been set up successfully.")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Activate the virtual environment:")
        if self.os_type == "Windows":
            logger.info("   venv\\Scripts\\activate")
        else:
            logger.info("   source venv/bin/activate")
        logger.info("2. Start the development server:")
        logger.info("   python manage.py runserver")
        logger.info("3. Access the admin interface at:")
        logger.info("   http://localhost:8000/admin/")
        logger.info("4. Use these credentials:")
        logger.info(
            f"   Phone: {self.config['initial_superuser'].get('phone_number', '+966555555555')}"
        )
        logger.info(
            f"   Password: {self.config['initial_superuser'].get('password', 'admin123')}"
        )
        logger.info("")
        logger.info("To start Celery worker:")
        logger.info("   celery -A queueme worker -l info")
        logger.info("")
        logger.info("To start Celery beat for scheduled tasks:")
        logger.info(
            "   celery -A queueme beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler"
        )
        logger.info("")
        logger.info("For more information, refer to the documentation.")
        logger.info("=" * 80)

    def run(self):
        """Run the complete setup process"""
        # Check prerequisites
        if not self.check_prerequisites():
            logger.error(
                "Prerequisites check failed. Please install required dependencies."
            )
            return False

        # Create virtual environment
        if not self.create_virtual_environment():
            logger.error("Failed to create virtual environment.")
            return False

        # Install dependencies
        if not self.install_dependencies():
            logger.error("Failed to install dependencies.")
            return False

        # Create .env file
        if not self.create_env_file():
            logger.error("Failed to create .env file.")
            return False

        # Apply migrations
        if not self.apply_migrations():
            logger.error("Failed to apply migrations.")
            return False

        # Load initial data
        if not self.load_initial_data():
            logger.warning("Failed to load initial data. Continuing anyway...")

        # Create superuser
        if not self.create_superuser():
            logger.error("Failed to create superuser.")
            return False

        # Test development server
        if not self.test_development_server():
            logger.warning("Failed to test development server. Continuing anyway...")

        # Setup Celery
        if not self.setup_celery():
            logger.warning("Failed to setup Celery. Continuing anyway...")

        # All done!
        self.setup_complete()
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Set up Queue Me development environment."
    )
    parser.add_argument(
        "--force", action="store_true", help="Force setup even if already completed"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail on any warning or error"
    )
    parser.add_argument(
        "--skip-data", action="store_true", help="Skip loading initial data"
    )
    args = parser.parse_args()

    setup = SetupDevelopment(args)

    try:
        success = setup.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\nSetup interrupted. You can continue later.")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
