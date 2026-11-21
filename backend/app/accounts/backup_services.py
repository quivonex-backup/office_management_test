import os
import shutil
import tempfile
import subprocess
import logging

from django.conf import settings
from django.core.files import File
from django.db import connection
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import DatabaseBackup

logger = logging.getLogger(__name__)

def get_mysql_config():

    db_config = connection.settings_dict

    if db_config.get("ENGINE") != "django.db.backends.mysql":
        raise ValueError("Database backup supports MySQL only.")

    return {
        "name": db_config.get("NAME"),
        "user": db_config.get("USER"),
        "password": db_config.get("PASSWORD"),
        "host": db_config.get("HOST") or "localhost",
        "port": str(db_config.get("PORT") or "3306"),
    }

def get_mysql_environment(config):

    env = os.environ.copy()

    # MYSQL_PWD avoids putting the database password
    # directly in the command-line arguments.
    env["MYSQL_PWD"] = config["password"] or ""

    return env

def get_mysql_command_arguments(config):

    return [
        "--user=" + config["user"],
        "--host=" + config["host"],
        "--port=" + config["port"],
        "--default-character-set=utf8mb4",
    ]

def create_database_backup(created_by):

    config = get_mysql_config()

    mysql_dump = (
        os.getenv("MYSQLDUMP_PATH")
        or shutil.which("mysqldump")
    )

    if not mysql_dump:
        raise RuntimeError(
            "mysqldump executable not found on the server."
        )

    temp_path = None
    backup = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".sql",
            prefix="office_management_backup_",
            delete=False
        ) as temp_file:

            temp_path = temp_file.name

            command = [
                mysql_dump,
                *get_mysql_command_arguments(config),
                "--single-transaction",
                "--quick",
                "--routines",
                "--triggers",
                "--events",
                "--hex-blob",
                "--add-drop-table",
                "--no-tablespaces",
                config["name"],
            ]

            result = subprocess.run(
                command,
                stdout=temp_file,
                stderr=subprocess.PIPE,
                env=get_mysql_environment(config),
                timeout=getattr(
                    settings,
                    "DATABASE_BACKUP_TIMEOUT",
                    3600
                ),
            )

            if result.returncode != 0:
                error = result.stderr.decode(
                    "utf-8",
                    errors="replace"
                )

                logger.error(
                    "MySQL backup failed: %s",
                    error
                )

                raise RuntimeError(
                    "Unable to generate MySQL database backup."
                )

        file_size = os.path.getsize(temp_path)

        if file_size <= 0:
            raise RuntimeError("Generated SQL backup is empty.")

        timestamp = timezone.localtime().strftime(
            "%d_%m_%y_%H_%M_%S"
        )

        filename = (
            f"office_management_backup_{timestamp}.sql"
        )

        backup = DatabaseBackup(
            created_by=created_by,
            file_size=file_size,
        )

        with open(temp_path, "rb") as sql_file:
            backup.file.save(
                filename,
                File(sql_file),
                save=False
            )

        backup.save()

        return backup

    except Exception:

        if backup and backup.file and backup.file.name:
            try:
                default_storage.delete(backup.file.name)
            except Exception:
                logger.exception(
                    "Failed to remove incomplete backup from storage."
                )

        raise

    finally:

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

def restore_database_from_upload(uploaded_file):

    config = get_mysql_config()

    mysql_client = (
        os.getenv("MYSQL_CLIENT_PATH")
        or shutil.which("mysql")
    )

    if not mysql_client:
        raise RuntimeError(
            "mysql client executable not found on the server."
        )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".sql",
            prefix="office_management_restore_",
            delete=False
        ) as temp_file:

            temp_path = temp_file.name

            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        if os.path.getsize(temp_path) <= 0:
            raise ValueError("Uploaded SQL file is empty.")

        command = [
            mysql_client,
            *get_mysql_command_arguments(config),
            config["name"],
        ]

        # Close Django's connection before replacing database tables.
        connection.close()

        with open(temp_path, "rb") as sql_file:

            result = subprocess.run(
                command,
                stdin=sql_file,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=get_mysql_environment(config),
                timeout=getattr(
                    settings,
                    "DATABASE_RESTORE_TIMEOUT",
                    3600
                ),
            )

        if result.returncode != 0:

            error = result.stderr.decode(
                "utf-8",
                errors="replace"
            )

            logger.error(
                "MySQL database restore failed: %s",
                error
            )

            raise RuntimeError(
                "Database restore failed. "
                "The database may be partially restored."
            )

        return True

    finally:

        connection.close()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
