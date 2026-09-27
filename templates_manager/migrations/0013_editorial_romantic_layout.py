"""
Layout «Editorial romântico» e os dois primeiros templates que o usam.

Idempotente: `update_or_create` pelo código e cópia das capas sobrescreve
sem duplicar. Uma categoria em falta (base nova, ainda sem
`seed_event_categories`) apenas faz saltar o respectivo template.
"""

from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations, models


COVER_DIR = "editorial"

TEMPLATES = [
    {
        "code": "editorial-terracota",
        "category": "casamento",
        "name": "Terracota Editorial",
        "description": "Fotografias de página inteira, aguarelas de peónias e papel rasgado num convite longo e cinematográfico.",
        "cover": "editorial-terracota.png",
        "primary": "#B8643F",
        "secondary": "#7D8B6A",
        "paper": "#FBF3EA",
        "ink": "#4A2E22",
        "display_font": '"Pinyon Script", "Great Vibes", cursive',
        "body_font": '"Cormorant Garamond", Georgia, serif',
        "google_fonts": "Pinyon+Script|Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500",
        "tags": "casamento, editorial, aguarela, fotografias, terracota, premium",
    },
    {
        "code": "noivado-editorial-rose",
        "category": "noivado",
        "name": "Promessa Editorial",
        "description": "Rosa antigo, aguarelas e as fotografias do casal numa narrativa romântica com abertura em papel rasgado.",
        "cover": "noivado-editorial-rose.png",
        "primary": "#B26A78",
        "secondary": "#7E8C79",
        "paper": "#FCF5F2",
        "ink": "#4B2E36",
        "display_font": '"Alex Brush", "Great Vibes", cursive',
        "body_font": '"EB Garamond", Georgia, serif',
        "google_fonts": "Alex+Brush|EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500",
        "tags": "noivado, editorial, aguarela, fotografias, rosé, premium",
    },
]


def _copy_cover(filename: str) -> None:
    source = Path(settings.BASE_DIR) / "static" / "img" / "templates" / COVER_DIR / filename
    destination_dir = Path(settings.MEDIA_ROOT) / "templates" / "covers" / COVER_DIR
    if not source.is_file():
        return
    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / filename)
    except OSError:
        # A capa pode ser carregada depois pela área de administração; a
        # falta de permissões no disco não deve travar o deploy.
        pass


def forwards(apps, schema_editor):
    Category = apps.get_model("events", "EventCategory")
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    for order, definition in enumerate(TEMPLATES, start=1):
        category = Category.objects.filter(code=definition["category"]).first()
        if category is None:
            continue
        _copy_cover(definition["cover"])
        template, _ = Template.objects.update_or_create(
            code=definition["code"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "layout": "editorial_romantico",
                "primary": definition["primary"],
                "secondary": definition["secondary"],
                "paper": definition["paper"],
                "ink": definition["ink"],
                "display_font": definition["display_font"],
                "body_font": definition["body_font"],
                "google_fonts": definition["google_fonts"],
                "has_cover": True,
                "has_countdown": True,
                "supports_music": True,
                "cover_image": f"templates/covers/{COVER_DIR}/{definition['cover']}",
                "tags": definition["tags"],
                "is_featured": True,
                "is_active": True,
                "display_order": order,
            },
        )
        template.categories.set([category])


def backwards(apps, schema_editor):
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    Template.objects.filter(code__in=[item["code"] for item in TEMPLATES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0010_add_engagement_category"),
        ("templates_manager", "0012_engagement_script_typography"),
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
                    ("evento_tematico", "Evento temático"),
                    ("noivado_elegante", "Noivado elegante"),
                    ("editorial_romantico", "Editorial romântico"),
                ],
                default="cartao_classico",
                help_text="A estrutura da página do convite.",
                max_length=40,
                verbose_name="layout",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
