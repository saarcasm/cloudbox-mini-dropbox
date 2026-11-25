import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from storage.storage_backend import S3StorageDriver


class Command(BaseCommand):
    help = (
        "Configure the AWS S3 bucket for CloudBox Free Tier: "
        "creates bucket if needed, blocks public access, enables AES-256 encryption, and sets CORS."
    )

    def handle(self, *args, **options):
        if not (settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY):
            raise CommandError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in the environment."
            )

        origins = [
            o.strip()
            for o in os.environ.get(
                "S3_CORS_ORIGINS",
                "https://cloudbox-mini-dropbox.vercel.app,http://localhost:5173",
            ).split(",")
            if o.strip()
        ]

        driver = S3StorageDriver()
        driver.ensure_bucket_configured(origins)
        self.stdout.write(
            self.style.SUCCESS(
                f"S3 bucket '{driver.bucket}' ({driver.region}) configured with "
                f"BlockPublicAccess, AES-256 encryption, and CORS for: {', '.join(origins)}"
            )
        )
