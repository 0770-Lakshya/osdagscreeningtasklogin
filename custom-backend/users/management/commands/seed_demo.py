"""seed the demo accounts - run after migrate

Every seeded file is a REAL file of its declared type: the .pdf files are
valid PDFs with correct xref offsets, the .png/.jpg are real images, and the
.docx is a real Word document (a docx is just a zip archive). This matters
because the demo ends with a download - a file that won't open makes a
working endpoint look broken.

Pass --reset to delete existing seed files and rebuild them.
"""
import io
import struct
import zipfile
import zlib
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from files.models import UserFile
from users.models import User
# ---------------------------------------------------------------- builders
def build_pdf(title, lines):
    """A minimal but valid PDF 1.4. Offsets in the xref table are computed
    as the objects are written, so the file is genuinely well-formed."""
    content = "BT /F1 16 Tf 60 760 Td (%s) Tj ET\n" % title
    y=728
    for line in lines:
        content += "BT /F1 11 Tf 60 %d Td (%s) Tj ET\n" % (y, line)
        y -= 18
    cb = content.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(cb)).encode() + b" >>\nstream\n" + cb + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n")

    xref_at = out.tell()
    out.write(b"xref\n0 " + str(len(objects) + 1).encode() + b"\n")
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(("%010d 00000 n \n" % off).encode())
    out.write(
        b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n"
    )
    return out.getvalue()

def build_png(width, height, rgb):
    """A real PNG: 8-bit truecolour, one solid fill, CRC per chunk."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF
        )
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )

# A real 1x1 baseline JPEG (SOI ... EOI), the smallest valid one.
JPEG_1PX = bytes([
    0xFF, 0xD8, 0xFF, 0xDB, 0x00, 0x43, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01, 0x11,
    0x00, 0xFF, 0xC4, 0x00, 0x14, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0xFF,
    0xC4, 0x00, 0x14, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xDA, 0x00, 0x08,
    0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0x37, 0xFF, 0xD9,
])


def build_docx(paragraphs):
    """A .docx is an OPC zip archive. Three parts is the valid minimum."""
    body = "".join(
        '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % p
        for p in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + body + "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


# ---------------------------------------------------------------- seed data
# same creds as the client's quick-fill buttons
SEED_USERS = [
    {
        "email": "alice@example.com",
        "password": "Password123!",
        "full_name": "Alice Nakamura",
        "files": [
            {
                "name": "resume_alice.pdf",
                "body": lambda: build_pdf(
                    "Alice Nakamura - Resume",
                    [
                        "Product manager.",
                        "",
                        "Seed file for the Osdag screening demo.",
                        "Generated by: manage.py seed_demo",
                    ],
                ),
            },
            {"name": "profile_photo.jpg", "body": lambda: JPEG_1PX},
        ],
    },
    {
        "email": "bob@example.com",
        "password": "Password123!",
        "full_name": "Bob Alvarez",
        "files": [
            {
                "name": "project_notes.txt",
                "body": lambda: (
                    "Project notes - Bob Alvarez\n"
                    "===========================\n\n"
                    "Seed file for the Osdag screening demo.\n"
                    "If you can are here for reading, the download endpoint streamed the bytes intact.\n"
                ).encode("utf-8"),
            },
            {
                "name": "invoice_march.pdf",
                "body": lambda: build_pdf(
                    "Invoice - March",
                    ["Bob Alvarez", "", "Seeded file for the Osdag screening demo."],
                ),
            },
        ],
    },
    {
        "email": "carol@example.com",
        "password": "Password123!",
        "full_name": "Carol Whitfield",
        "files": [
            {
                "name": "test_plan.docx",
                "body": lambda: build_docx(
                    [
                        "Test Plan - Carol Whitfield",
                        "",
                        "Seeded file for the Osdag screening demo.",
                        "Data isolation means each user sees only their own files.",
                    ]
                ),
            },
            {"name": "vacation.png", "body": lambda: build_png(64, 64, (156, 58, 32))},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed demo users and their files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="delete existing seed files first, then rebuild them",
        )

    def handle(self, *args, **options):
        for entry in SEED_USERS:
            email = entry["email"]
            user, created = User.objects.get_or_create(
                email=email, defaults={"full_name": entry["full_name"]}
            )
            if created or not user.check_password(entry["password"]):
                user.set_password(entry["password"])
                user.full_name = entry["full_name"]
                user.save(update_fields=["password", "full_name"])

            if options["reset"]:
                names = [f["name"] for f in entry["files"]]
                removed = UserFile.objects.filter(owner=user, name__in=names)
                for old in removed:
                    old.content.delete(save=False)
                count = removed.count()
                removed.delete()
                if count:
                    self.stdout.write(f"  removed {count} old file(s) for {email}")

            created_files = 0
            for f in entry["files"]:
                if UserFile.objects.filter(owner=user, name=f["name"]).exists():
                    continue
                raw = f["body"]()
                UserFile.objects.create(
                    owner=user,
                    name=f["name"],
                    des=f"Seed file: {f['name']}",
                    # size is the REAL byte count, not a made-up number
                    size=len(raw),
                    content=ContentFile(raw, name=f["name"]),
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
