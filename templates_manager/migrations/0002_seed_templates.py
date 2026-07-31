"""
Semeia o catálogo de templates de convite.

Dois templates completos, com layout próprio, feitos pela equipa
MeuConvite — e um conjunto de paletas sobre o layout «cartão clássico»,
para haver variedade de cores desde o início.
"""

from __future__ import annotations

from django.db import migrations

SERIF = '"Playfair Display", Georgia, serif'
SCRIPT = '"Great Vibes", cursive'
BODY = '"Cormorant Garamond", Georgia, serif'
SANS = '"Montserrat", "Segoe UI", sans-serif'

FONTS_SCRIPT = "Great+Vibes|Cormorant+Garamond:wght@400;600"
FONTS_SERIF = "Playfair+Display:wght@500;600|Cormorant+Garamond:wght@400;600"
FONTS_SANS = "Montserrat:wght@300;400;600|Cormorant+Garamond:wght@400;600"

# --- Os dois templates completos -------------------------------------
FEATURED = [
    {
        "code": "carta-selada",
        "name": "Carta Selada",
        "description": (
            "Abre como um envelope lacrado: capa com selo, contagem regressiva "
            "e o convite a revelar-se por secções."
        ),
        "layout": "carta_selada",
        "primary": "#7B1E3A",
        "secondary": "#D9C39A",
        "paper": "#FBF6EF",
        "ink": "#3D2A2F",
        "display_font": SERIF,
        "body_font": BODY,
        "google_fonts": FONTS_SERIF,
        "tags": "elegante, bordeaux, lacre, noite",
        "is_featured": True,
        "display_order": 10,
    },
    {
        "code": "envelope-botanico",
        "name": "Envelope Botânico",
        "description": (
            "Papel de linho, folhagem desenhada à mão e um programa em linha "
            "do tempo. Leve, claro e muito legível no telemóvel."
        ),
        "layout": "envelope_botanico",
        "primary": "#6B7F42",
        "secondary": "#C8A96A",
        "paper": "#FBFAF4",
        "ink": "#3F4A32",
        "display_font": SCRIPT,
        "body_font": BODY,
        "google_fonts": FONTS_SCRIPT,
        "tags": "botânico, natural, claro, ar livre",
        "is_featured": True,
        "display_order": 20,
    },
]

# --- Paletas sobre o cartão clássico ---------------------------------
PALETTES = [
    ("classico-dourado", "Clássico Dourado", "Branco e dourado, sóbrio e intemporal.",
     "#C8A96A", "#1F2933", "#FFFDF8", "#3A3226", SCRIPT, FONTS_SCRIPT, "clássico, dourado"),
    ("luxo-preto", "Luxo Preto e Dourado", "Fundo escuro com letras douradas, para celebrações de gala.",
     "#D4AF37", "#111111", "#15130F", "#F2E6C8", SERIF, FONTS_SERIF, "luxo, noite"),
    ("capulana", "Capulana Moçambicana", "Inspirado nas cores vivas das capulanas.",
     "#C1502E", "#1B6B5A", "#FFF6EC", "#43281C", SERIF, FONTS_SERIF, "tradicional, moçambique"),
    ("floral-rosa", "Floral Rosa", "Aguarelas florais em tons de rosa velho.",
     "#B76E79", "#6D4B52", "#FDFAF7", "#6D4B52", SCRIPT, FONTS_SCRIPT, "floral, romântico"),
    ("minimal-branco", "Minimalista Branco", "Muito espaço em branco e tipografia limpa.",
     "#2F2F2F", "#9A9A9A", "#FFFFFF", "#2F2F2F", SANS, FONTS_SANS, "minimal, moderno"),
    ("azul-marinho", "Azul Marinho e Prata", "Azul profundo com detalhes prateados.",
     "#1F3A5F", "#A8B6C4", "#F7F9FC", "#1F3A5F", SERIF, FONTS_SERIF, "formal, clássico"),
    ("terracota", "Terracota e Areia", "Tons quentes de terra, com folhas secas.",
     "#B5651D", "#7A5230", "#FDF6EE", "#5B3A21", SCRIPT, FONTS_SCRIPT, "boho, quente"),
    ("tropical", "Tropical", "Folhas de palmeira e coral, com o sabor da costa.",
     "#12796A", "#E4693F", "#F6FFFC", "#0F3D36", SCRIPT, FONTS_SCRIPT, "praia, tropical"),
    ("lavanda", "Lavanda", "Lilás suave sobre cinza claro.",
     "#8B7BB8", "#5C5470", "#FBFAFE", "#4A4458", SCRIPT, FONTS_SCRIPT, "suave, primavera"),
    ("areia-dourada", "Areia Dourada", "Areia, sol e mar ao fim da tarde.",
     "#D9A441", "#2E6E8E", "#FFFCF3", "#5A4520", SCRIPT, FONTS_SCRIPT, "praia, verão"),
    ("noite-estrelada", "Noite Estrelada", "Azul da meia-noite com pontos dourados.",
     "#E8C86A", "#101A33", "#141C33", "#EDE7D6", SERIF, FONTS_SERIF, "noite, luxo"),
]


def forwards(apps, schema_editor) -> None:
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")

    for definition in FEATURED:
        InvitationTemplate.objects.update_or_create(
            code=definition["code"], defaults=definition
        )

    for order, palette in enumerate(PALETTES, start=1):
        code, name, description, primary, secondary, paper, ink, display, fonts, tags = palette
        InvitationTemplate.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "layout": "cartao_classico",
                "primary": primary,
                "secondary": secondary,
                "paper": paper,
                "ink": ink,
                "display_font": display,
                "body_font": BODY,
                "google_fonts": fonts,
                "tags": tags,
                "is_featured": False,
                "display_order": 100 + order * 10,
            },
        )


def backwards(apps, schema_editor) -> None:
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    codes = [definition["code"] for definition in FEATURED] + [row[0] for row in PALETTES]
    InvitationTemplate.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("templates_manager", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
