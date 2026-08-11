from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations, models


COLLECTIONS = {
    "lobolo": [
        ("lobolo-heranca-dourada", "Herança Dourada", "Capulana, tradição e elegância para unir duas famílias.", "heranca-dourada.png", "#B68A3A", "#5C101D", "#FBF4E7", "#2D1714"),
        ("lobolo-encontro-familias", "Encontro das Famílias", "Calor moçambicano e acolhimento para a cerimónia tradicional.", "encontro-familias.png", "#D48032", "#6B2D18", "#FFF7EC", "#301B13"),
        ("lobolo-raizes-mocambique", "Raízes de Moçambique", "Verde profundo, cobre e raízes que celebram a ancestralidade.", "raizes-mocambique.png", "#B8753E", "#123B2A", "#F5EBDD", "#183027"),
    ],
    "aniversario": [
        ("aniversario-festa-vibrante", "Festa Vibrante", "Cor, balões e energia para aniversários alegres.", "festa-vibrante.png", "#FF6B5F", "#214BB8", "#FFF4E8", "#1E2742"),
        ("aniversario-noite-neon", "Noite Neon", "Luzes intensas para festas modernas e celebrações noturnas.", "noite-neon.png", "#F128D4", "#25105B", "#F8F1FF", "#261738"),
        ("aniversario-marco-dourado", "Marco Dourado", "Um visual sóbrio e luxuoso para celebrar datas marcantes.", "marco-dourado.png", "#C99A42", "#6F4D21", "#FFF9EE", "#332719"),
    ],
    "batismo": [
        ("batismo-luz-serena", "Luz Serena", "Branco e azul para uma celebração de fé luminosa.", "luz-serena.png", "#8DBDD3", "#547A91", "#FBFDFC", "#29404B"),
        ("batismo-agua-e-fe", "Água e Fé", "Reflexos suaves e natureza para o momento do batismo.", "agua-e-fe.png", "#75BCCC", "#6A9189", "#F7FCFC", "#29464A"),
        ("batismo-branco-celestial", "Branco Celestial", "Marfim e pequenos apontamentos dourados, delicados e solenes.", "branco-celestial.png", "#C8A45B", "#9C825C", "#FFFCF5", "#4B4032"),
    ],
    "formatura": [
        ("graduacao-conquista-academica", "Conquista Académica", "Azul e dourado para celebrar uma grande conquista.", "conquista-academica.png", "#D5A84B", "#10254B", "#F9F5EC", "#15233D"),
        ("graduacao-futuro-movimento", "Futuro em Movimento", "Linhas contemporâneas para quem começa uma nova etapa.", "futuro-movimento.png", "#27B9D0", "#1352A2", "#F3FAFD", "#173656"),
        ("graduacao-merito-esmeralda", "Mérito Esmeralda", "Verde e ouro num convite de distinção académica.", "merito-esmeralda.png", "#C6A34B", "#075239", "#F7F5E8", "#16382E"),
    ],
    "cha-de-bebe": [
        ("cha-bebe-nuvem-doce", "Nuvem Doce", "Nuvens, lua e estrelas para receber o bebé com ternura.", "nuvem-doce.png", "#E8AEBA", "#89B7D1", "#FFF8F3", "#46566A"),
        ("cha-bebe-jardim", "Jardim do Bebé", "Folhagem e flores suaves para uma receção delicada.", "jardim-bebe.png", "#D79E84", "#78927A", "#FBF8F0", "#3E5145"),
        ("cha-bebe-minimal", "Minimal Bebé", "Tons neutros e formas naturais num estilo moderno.", "minimal-bebe.png", "#C47855", "#9A8268", "#FBF5EA", "#554438"),
    ],
    "outro": [
        ("outro-celebracao-livre", "Celebração Livre", "Uma moldura colorida para qualquer ocasião especial.", "celebracao-livre.png", "#E9695B", "#5940A6", "#FFF3DB", "#382B4B"),
        ("outro-essencial-moderno", "Essencial Moderno", "Geometria sóbria para eventos contemporâneos e versáteis.", "essencial-moderno.png", "#B36C42", "#252321", "#F5F0E8", "#282522"),
        ("outro-noite-criativa", "Noite Criativa", "Cristal e luz para encontros culturais e eventos noturnos.", "noite-criativa.png", "#8D55E8", "#081A3A", "#F4F3FA", "#18223A"),
    ],
}


def forwards(apps, schema_editor):
    Category = apps.get_model("events", "EventCategory")
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    wedding = Category.objects.filter(code="casamento").first()
    corporate_codes = ["corporate-executive-summit", "corporate-innovation-forum", "corporate-gala"]
    thematic_codes = [item[0] for items in COLLECTIONS.values() for item in items]
    if wedding:
        for template in Template.objects.exclude(code__in=corporate_codes + thematic_codes):
            template.categories.set([wedding])
    source_root = Path(settings.BASE_DIR) / "static" / "img" / "templates" / "themes"
    media_root = Path(settings.MEDIA_ROOT) / "templates" / "covers" / "themes"
    for category_code, items in COLLECTIONS.items():
        category = Category.objects.filter(code=category_code).first()
        if not category:
            continue
        destination_dir = media_root / category_code
        destination_dir.mkdir(parents=True, exist_ok=True)
        for order, (code, name, description, filename, primary, secondary, paper, ink) in enumerate(items, 1):
            source = source_root / category_code / filename
            destination = destination_dir / filename
            if source.is_file():
                shutil.copy2(source, destination)
            template, _ = Template.objects.update_or_create(code=code, defaults={
                "name": name, "description": description, "layout": "evento_tematico",
                "primary": primary, "secondary": secondary, "paper": paper, "ink": ink,
                "display_font": '"Playfair Display", Georgia, serif',
                "body_font": '"Inter", Arial, sans-serif',
                "google_fonts": "Playfair+Display:wght@600;700|Inter:wght@400;500;600;700",
                "has_cover": True, "has_countdown": True, "supports_music": True,
                "cover_image": f"templates/covers/themes/{category_code}/{filename}",
                "tags": f"{category_code}, celebração, evento", "is_featured": True,
                "is_active": True, "display_order": order * 10,
            })
            template.categories.set([category])


def backwards(apps, schema_editor):
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    Template.objects.filter(code__in=[item[0] for items in COLLECTIONS.values() for item in items]).delete()


class Migration(migrations.Migration):
    dependencies = [("events", "0009_category_specific_fields_and_order"), ("templates_manager", "0009_corporate_template_collection")]
    operations = [
        migrations.AlterField(model_name="invitationtemplate", name="layout", field=models.CharField(choices=[("carta_selada", "Carta selada (abertura animada)"), ("envelope_botanico", "Envelope botânico"), ("cartao_classico", "Cartão clássico"), ("corporativo", "Evento corporativo"), ("evento_tematico", "Evento temático")], default="cartao_classico", help_text="A estrutura da página do convite.", max_length=40, verbose_name="layout")),
        migrations.RunPython(forwards, backwards),
    ]
