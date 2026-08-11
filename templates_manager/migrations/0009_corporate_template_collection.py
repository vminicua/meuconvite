from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations, models


CORPORATE_TEMPLATES = [
    {
        "code": "corporate-executive-summit",
        "name": "Executive Summit",
        "description": "Arquitectura luminosa e azul para conferências, fóruns executivos e encontros institucionais.",
        "primary": "#35BDF5",
        "secondary": "#0B2E66",
        "paper": "#F5F9FD",
        "ink": "#10243E",
        "cover": "executive-summit-cover-v1.png",
        "order": 10,
    },
    {
        "code": "corporate-innovation-forum",
        "name": "Innovation Forum",
        "description": "Dados, tecnologia e movimento para seminários, workshops e lançamentos de inovação.",
        "primary": "#22C7A9",
        "secondary": "#0B1826",
        "paper": "#F3FAF8",
        "ink": "#102A2A",
        "cover": "innovation-forum-cover-v1.png",
        "order": 20,
    },
    {
        "code": "corporate-gala",
        "name": "Corporate Gala",
        "description": "Preto e dourado para galas empresariais, prémios, jantares e lançamentos premium.",
        "primary": "#D6A84F",
        "secondary": "#171411",
        "paper": "#FBF7EF",
        "ink": "#2B241B",
        "cover": "corporate-gala-cover-v1.png",
        "order": 30,
    },
]


def forwards(apps, schema_editor):
    EventCategory = apps.get_model("events", "EventCategory")
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    corporate = EventCategory.objects.filter(code="evento-corporativo").first()
    if corporate is None:
        return

    non_corporate = list(EventCategory.objects.exclude(pk=corporate.pk))
    corporate_codes = {item["code"] for item in CORPORATE_TEMPLATES}
    for template in InvitationTemplate.objects.exclude(code__in=corporate_codes):
        if not template.categories.exists():
            template.categories.set(non_corporate)

    source_dir = Path(settings.BASE_DIR) / "static" / "img" / "templates" / "corporate"
    media_dir = Path(settings.MEDIA_ROOT) / "templates" / "covers" / "corporate"
    media_dir.mkdir(parents=True, exist_ok=True)

    for definition in CORPORATE_TEMPLATES:
        filename = definition["cover"]
        source = source_dir / filename
        destination = media_dir / filename
        if source.is_file() and not destination.is_file():
            shutil.copy2(source, destination)
        template, _ = InvitationTemplate.objects.update_or_create(
            code=definition["code"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "layout": "corporativo",
                "primary": definition["primary"],
                "secondary": definition["secondary"],
                "paper": definition["paper"],
                "ink": definition["ink"],
                "display_font": '"Manrope", Arial, sans-serif',
                "body_font": '"Inter", Arial, sans-serif',
                "google_fonts": "Manrope:wght@600;700;800|Inter:wght@400;500;600;700",
                "has_cover": True,
                "has_countdown": True,
                "supports_music": False,
                "cover_image": f"templates/covers/corporate/{filename}",
                "tags": "corporativo, empresa, conferência, negócios",
                "is_featured": True,
                "is_active": True,
                "display_order": definition["order"],
            },
        )
        template.categories.set([corporate])


def backwards(apps, schema_editor):
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    InvitationTemplate.objects.filter(
        code__in=[item["code"] for item in CORPORATE_TEMPLATES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0008_refine_corporate_category"),
        ("templates_manager", "0008_wedding_script_typography"),
    ]
    operations = [
        migrations.AlterField(
            model_name="invitationtemplate",
            name="layout",
            field=models.CharField(
                choices=[
                    ("carta_selada", "Carta selada (abertura animada)"),
                    ("envelope_botanico", "Envelope botânico"),
                    ("cartao_classico", "Cartão clássico"),
                    ("corporativo", "Evento corporativo"),
                ],
                default="cartao_classico",
                help_text="A estrutura da página do convite.",
                max_length=40,
                verbose_name="layout",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
