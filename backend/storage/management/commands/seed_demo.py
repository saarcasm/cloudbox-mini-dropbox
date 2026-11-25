import io
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from storage.models import Folder, ShareLink, StoredFile
from storage.storage_backend import get_storage_driver

User = get_user_model()


SAMPLE_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="760" height="420" viewBox="0 0 760 420">
  <rect width="760" height="420" fill="#f8fafc" rx="16"/>
  <text x="380" y="42" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="bold" fill="#0f172a">
    CloudBox (Mini Dropbox) - System Architecture
  </text>
  <rect x="275" y="70" width="210" height="44" rx="10" fill="#fef3c7" stroke="#d97706" stroke-width="1.5"/>
  <text x="380" y="97" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="600" fill="#92400e">User (Web / Mobile)</text>
  <line x1="380" y1="114" x2="380" y2="144" stroke="#334155" stroke-width="2"/>
  <rect x="255" y="144" width="250" height="46" rx="10" fill="#e0f2fe" stroke="#0284c7" stroke-width="1.5"/>
  <text x="380" y="172" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="600" fill="#0369a1">Frontend (React.js + Vite)</text>
  <line x1="380" y1="190" x2="380" y2="220" stroke="#334155" stroke-width="2"/>
  <rect x="190" y="220" width="380" height="54" rx="10" fill="#dcfce7" stroke="#16a34a" stroke-width="1.5"/>
  <text x="380" y="244" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="600" fill="#166534">Backend API (Django REST Framework)</text>
  <text x="380" y="263" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#15803d">Auth | File Management | Sharing</text>
  <line x1="270" y1="274" x2="170" y2="318" stroke="#334155" stroke-width="2"/>
  <line x1="490" y1="274" x2="590" y2="318" stroke="#334155" stroke-width="2"/>
  <rect x="55" y="318" width="230" height="58" rx="10" fill="#ede9fe" stroke="#7c3aed" stroke-width="1.5"/>
  <text x="170" y="344" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="600" fill="#5b21b6">Database</text>
  <text x="170" y="362" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#6d28d9">MySQL / SQLite (Users &amp; Metadata)</text>
  <rect x="475" y="318" width="230" height="58" rx="10" fill="#fce7f3" stroke="#db2777" stroke-width="1.5"/>
  <text x="590" y="344" text-anchor="middle" font-family="sans-serif" font-size="13" font-weight="600" fill="#9d174d">Cloud Storage Bucket</text>
  <text x="590" y="362" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#be185d">AWS S3 / AES-256 Encrypted Objects</text>
</svg>
"""

PROJECT_NOTES = b"""CloudBox (Mini Dropbox) - CSE Mini Project Notes
==============================================
Submitted by: Saar Ravindra Singh, Rohan Tiwari, Saksham Garg
Submitted to: Mr. Mradul Jain (CSE Deptt.)

Key Highlights:
1. React.js responsive frontend supporting mobile and desktop viewports.
2. Django REST Framework API with Token Authentication and Admin quota controls.
3. Unified Cloud Storage layer: AWS S3 (AES-256 at rest) + local S3-compatible bucket.
4. Chunked file uploads with automatic retry for files up to 100 MB.
5. Shareable public download links for both files and folders (.zip export).
"""

SAMPLE_CSV = b"""metric,target,status
Max File Upload Size,100 MB,Supported (Chunked + Retry)
Encryption at Rest,AES-256,Enabled
Concurrent Users Target,1000+,Stateless REST API
Uptime & Reconnect,99% with Auto-Retry,3x Chunk Retry
"""


class Command(BaseCommand):
    help = "Seed demo users, folders, sample files, and share links for live presentation."

    def handle(self, *args, **options):
        driver = get_storage_driver()

        demo_accounts = [
            {
                "username": "saar",
                "email": "saar@cloudbox.edu",
                "first_name": "Saar Ravindra Singh",
                "is_staff": True,
                "quota_mb": 1024,
            },
            {
                "username": "rohan",
                "email": "rohan@cloudbox.edu",
                "first_name": "Rohan Tiwari",
                "is_staff": False,
                "quota_mb": 500,
            },
            {
                "username": "saksham",
                "email": "saksham@cloudbox.edu",
                "first_name": "Saksham Garg",
                "is_staff": False,
                "quota_mb": 500,
            },
        ]

        users = {}
        for acct in demo_accounts:
            user, created = User.objects.get_or_create(
                username=acct["username"],
                defaults={
                    "email": acct["email"],
                    "first_name": acct["first_name"],
                    "is_staff": acct["is_staff"],
                },
            )
            if created:
                user.set_password("demo1234")
                user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.storage_quota_bytes = acct["quota_mb"] * 1024 * 1024
            profile.save(update_fields=["storage_quota_bytes"])
            users[acct["username"]] = user

        saar = users["saar"]

        # Seed folders and sample files for primary presenter account if empty
        if StoredFile.objects.filter(owner=saar).count() == 0:
            notes_folder, _ = Folder.objects.get_or_create(
                owner=saar, name="CSE Project Docs", parent=None
            )
            diagrams_folder, _ = Folder.objects.get_or_create(
                owner=saar, name="Architecture Diagrams", parent=None
            )

            samples = [
                (notes_folder, "CloudBox_Project_Summary.txt", "text/plain", PROJECT_NOTES),
                (notes_folder, "NFR_Benchmarks.csv", "text/csv", SAMPLE_CSV),
                (diagrams_folder, "System_Architecture.svg", "image/svg+xml", SAMPLE_SVG),
                (None, "Welcome_to_CloudBox.txt", "text/plain", PROJECT_NOTES),
            ]

            created_files = []
            for idx, (folder, name, ctype, raw) in enumerate(samples):
                file_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"cloudbox-demo-{saar.username}-{idx}-{name}")
                key = f"users/{saar.id}/{file_id}"
                size_bytes, checksum = driver.save_file(key, io.BytesIO(raw), ctype)
                sf, _ = StoredFile.objects.update_or_create(
                    id=file_id,
                    defaults={
                        "owner": saar,
                        "folder": folder,
                        "name": name,
                        "object_key": key,
                        "size_bytes": size_bytes,
                        "content_type": ctype,
                        "checksum_sha256": checksum,
                        "encrypted_at_rest": True,
                    },
                )
                created_files.append(sf)

            # Create sample active share links for demo
            ShareLink.objects.get_or_create(
                owner=saar,
                file=created_files[2],
                defaults={"is_active": True},
            )
            ShareLink.objects.get_or_create(
                owner=saar,
                folder=notes_folder,
                defaults={"is_active": True},
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully (password: demo1234)."))
