import os
import zipfile
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.conf import settings


class Command(BaseCommand):
    help = "Створює ZIP-архів SQLite бази даних та надсилає його на email"

    def handle(self, *args, **options):
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        db_path = str(settings.DATABASES["default"]["NAME"])
        backup_filename = f"warehouse_db_{date_str}.zip"

        self.stdout.write("Створення ZIP-архіву бази даних...")

        # Пакуємо базу у звичайний ZIP
        with zipfile.ZipFile(backup_filename, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Всередині архіву файл називатиметься warehouse_db.sqlite3
            zip_file.write(db_path, arcname="warehouse_db.sqlite3")

        recipient_email = getattr(settings, "BACKUP_RECEIVER_EMAIL", settings.EMAIL_HOST_USER)
        self.stdout.write(f"Надсилання листа на {recipient_email}...")

        email = EmailMessage(
            subject=f"📦 Резервна копія складу — {date_str}",
            body=f"Автоматичний ZIP-бекап бази даних складу від {date_str}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )

        with open(backup_filename, "rb") as f:
            email.attach(backup_filename, f.read(), "application/zip")

        email.send()

        # Видаляємо тимчасовий архів
        if os.path.exists(backup_filename):
            os.remove(backup_filename)

        self.stdout.write(self.style.SUCCESS("✓ ZIP-бекап успішно надіслано на пошту!"))
