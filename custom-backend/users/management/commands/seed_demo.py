"""seed the demo accounts - run after migrate"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from files.models import UserFile
from users.models import User

# same creds as the client's quick-fill buttons
SEED_USERS = [
    {
        "email": "alice@example.com",
        "password": "Password123!",
        "full_name": "Alice Nakamura",
        "files": [
            {"name": "resume_alice.pdf", "mime": "application/pdf", "size": 84213},
            {"name": "profile_photo.jpg", "mime": "image/jpeg", "size": 231044},
        ],
    },
    {
        "email": "bob@example.com",
        "password": "Password123!",
        "full_name": "Bob Alvarez",
        "files": [
            {"name": "project_notes.txt", "mime": "text/plain", "size": 5210},
            {"name": "invoice_march.pdf", "mime": "application/pdf", "size": 62890},
        ],
    },
    {
        "email": "carol@example.com",
        "password": "Password123!",
        "full_name": "Carol Whitfield",
        "files": [
            {
                "name": "test_plan.docx",
                "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "size": 41200,
            },
            {"name": "vacation.png", "mime": "image/png", "size": 512300},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed demo users"

    def handle(self, *args, **options):
        for entry in SEED_USERS:
            email = entry["email"]
            user, created = User.objects.get_or_create(
                email=email, defaults={"full_name": entry["full_name"]}
            )
            if created or not user.check_password(entry["password"]):
                user.set_password(entry["password"])
                user.save(update_fields=["password", "full_name"])

            created_files = 0
            for f in entry["files"]:
                if UserFile.objects.filter(owner=user, name=f["name"]).exists():
                    continue
                body = f"Placeholder file for {f['name']}\n"
                UserFile.objects.create(
                    owner=user,
                    name=f["name"],
                    des=f"Seed file: {f['name']}",
                    size=f["size"],
                    content=ContentFile(body.encode("utf-8"), name=f["name"]),
                )
                created_files += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"{'created' if created else 'exists'} {email} - {created_files} files"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nTest accounts:"))
        for entry in SEED_USERS:
            self.stdout.write(f"  {entry['email']} / {entry['password']}")
