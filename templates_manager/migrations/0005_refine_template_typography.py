from django.db import migrations


TYPOGRAPHY = {
    "carta-selada": (
        '"Italianno", "Segoe Script", cursive',
        '"Cormorant Garamond", Georgia, serif',
        "Italianno|Cormorant+Garamond:wght@400;500;600",
    ),
    "envelope-botanico": (
        '"Great Vibes", "Segoe Script", cursive',
        '"Cormorant Garamond", Georgia, serif',
        "Great+Vibes|Cormorant+Garamond:wght@400;500;600",
    ),
    "classico-dourado": (
        '"Cinzel", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cinzel:wght@400;500;600|Cormorant+Garamond:wght@400;500;600",
    ),
    "luxo-preto": (
        '"Cinzel", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cinzel:wght@400;500;600|Cormorant+Garamond:wght@400;500;600",
    ),
    "capulana": (
        '"Cinzel", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cinzel:wght@400;500;600|Cormorant+Garamond:wght@400;500;600",
    ),
    "floral-rosa": (
        '"Great Vibes", "Segoe Script", cursive',
        '"Cormorant Garamond", Georgia, serif',
        "Great+Vibes|Cormorant+Garamond:wght@400;500;600",
    ),
    "minimal-branco": (
        '"Cormorant Garamond", Georgia, serif',
        '"Montserrat", "Segoe UI", sans-serif',
        "Cormorant+Garamond:wght@400;500;600|Montserrat:wght@300;400;500;600",
    ),
    "azul-marinho": (
        '"Cinzel", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cinzel:wght@400;500;600|Cormorant+Garamond:wght@400;500;600",
    ),
    "terracota": (
        '"Cormorant Garamond", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cormorant+Garamond:wght@400;500;600",
    ),
    "tropical": (
        '"Cormorant Garamond", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cormorant+Garamond:wght@400;500;600",
    ),
    "lavanda": (
        '"Cormorant Garamond", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cormorant+Garamond:wght@400;500;600",
    ),
    "areia-dourada": (
        '"Cormorant Garamond", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cormorant+Garamond:wght@400;500;600",
    ),
    "noite-estrelada": (
        '"Cinzel", Georgia, serif',
        '"Cormorant Garamond", Georgia, serif',
        "Cinzel:wght@400;500;600|Cormorant+Garamond:wght@400;500;600",
    ),
}


def apply_typography(apps, schema_editor):
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    for code, (display_font, body_font, google_fonts) in TYPOGRAPHY.items():
        InvitationTemplate.objects.filter(code=code).update(
            display_font=display_font,
            body_font=body_font,
            google_fonts=google_fonts,
        )


def reverse_typography(apps, schema_editor):
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    script_codes = {
        "envelope-botanico",
        "classico-dourado",
        "floral-rosa",
        "terracota",
        "tropical",
        "lavanda",
        "areia-dourada",
    }
    for code in TYPOGRAPHY:
        if code == "minimal-branco":
            display_font = '"Montserrat", "Segoe UI", sans-serif'
            google_fonts = "Montserrat:wght@300;400;600|Cormorant+Garamond:wght@400;600"
        elif code in script_codes:
            display_font = '"Great Vibes", cursive'
            google_fonts = "Great+Vibes|Cormorant+Garamond:wght@400;600"
        else:
            display_font = '"Playfair Display", Georgia, serif'
            google_fonts = "Playfair+Display:wght@500;600|Cormorant+Garamond:wght@400;600"
        InvitationTemplate.objects.filter(code=code).update(
            display_font=display_font,
            body_font='"Cormorant Garamond", Georgia, serif',
            google_fonts=google_fonts,
        )


class Migration(migrations.Migration):
    dependencies = [("templates_manager", "0004_require_template_covers")]

    operations = [migrations.RunPython(apply_typography, reverse_typography)]
