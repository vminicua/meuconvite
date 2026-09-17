from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations, models


TEMPLATES = [
    ("noivado-pedido-de-ouro", "Pedido de Ouro", "Champanhe, seda e luz dourada para um pedido inesquecível.", "pedido-de-ouro.png", "#C7A15A", "#5A4430", "#FFF9EF", "#352B22", '"Bodoni Moda", Georgia, serif'),
    ("noivado-jardim-promessas", "Jardim de Promessas", "Flores brancas e verde sálvia num convite leve e romântico.", "jardim-de-promessas.png", "#87977A", "#B18A4A", "#FBFAF4", "#354035", '"Cormorant Garamond", Georgia, serif'),
    ("noivado-safira-eterna", "Safira Eterna", "Azul profundo, prata e veludo para uma celebração verdadeiramente distinta.", "safira-eterna.png", "#9CB5D1", "#091C3B", "#F5F8FC", "#17283E", '"Playfair Display", Georgia, serif'),
    ("noivado-rose-contemporaneo", "Rosé Contemporâneo", "Blush, cristal e rosé gold num desenho moderno e delicado.", "rose-contemporaneo.png", "#C98F87", "#8B5A55", "#FFF7F5", "#493535", '"Bodoni Moda", Georgia, serif'),
    ("noivado-noite-veludo", "Noite de Veludo", "Bordô, preto e ouro antigo para um noivado de atmosfera cinematográfica.", "noite-de-veludo.png", "#C49A57", "#4A0E1C", "#FCF7F0", "#2A171B", '"Cormorant Garamond", Georgia, serif'),
    ("noivado-marfim-minimalista", "Marfim Minimalista", "Texturas naturais e silêncio visual para um luxo simples e intemporal.", "marfim-minimalista.png", "#BDA67F", "#716453", "#FFFCF6", "#37322C", '"DM Serif Display", Georgia, serif'),
    ("noivado-capulana-amor", "Capulana de Amor", "Geometria moçambicana, terracota e dourado numa composição elegante.", "capulana-de-amor.png", "#C8794D", "#0E5D5A", "#FFF6E8", "#352A22", '"Playfair Display", Georgia, serif'),
]


def forwards(apps, schema_editor):
    Category = apps.get_model("events", "EventCategory")
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    category = Category.objects.filter(code="noivado").first()
    if category is None:
        return

    source_dir = Path(settings.BASE_DIR) / "static" / "img" / "templates" / "engagement"
    media_dir = Path(settings.MEDIA_ROOT) / "templates" / "covers" / "engagement"
    media_dir.mkdir(parents=True, exist_ok=True)
    for order, definition in enumerate(TEMPLATES, start=1):
        code, name, description, filename, primary, secondary, paper, ink, display_font = definition
        source = source_dir / filename
        destination = media_dir / filename
        if source.is_file():
            shutil.copy2(source, destination)
        template, _ = Template.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "layout": "noivado_elegante",
                "primary": primary,
                "secondary": secondary,
                "paper": paper,
                "ink": ink,
                "display_font": display_font,
                "body_font": '"Montserrat", Arial, sans-serif',
                "google_fonts": "Bodoni+Moda:opsz,wght@6..96,400;600|Cormorant+Garamond:wght@400;600|DM+Serif+Display|Playfair+Display:wght@500;700|Montserrat:wght@400;500;600;700",
                "has_cover": True,
                "has_countdown": True,
                "supports_music": True,
                "cover_image": f"templates/covers/engagement/{filename}",
                "tags": "noivado, elegante, romântico, premium",
                "is_featured": order <= 2,
                "is_active": True,
                "display_order": order * 10,
            },
        )
        template.categories.set([category])


def backwards(apps, schema_editor):
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    Template.objects.filter(code__in=[item[0] for item in TEMPLATES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0010_add_engagement_category"),
        ("templates_manager", "0010_category_template_collections"),
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
                ],
                default="cartao_classico",
                help_text="A estrutura da página do convite.",
                max_length=40,
                verbose_name="layout",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
