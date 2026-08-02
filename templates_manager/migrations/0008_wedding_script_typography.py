from django.db import migrations


TYPOGRAPHY = {
    "carta-selada": ("Italianno", "Italianno"),
    "envelope-botanico": ("Great Vibes", "Great+Vibes"),
    "classico-dourado": ("Allura", "Allura"),
    "luxo-preto": ("Parisienne", "Parisienne"),
    "capulana": ("Allura", "Allura"),
    "floral-rosa": ("Great Vibes", "Great+Vibes"),
    "minimal-branco": ("Parisienne", "Parisienne"),
    "azul-marinho": ("Allura", "Allura"),
    "terracota": ("Great Vibes", "Great+Vibes"),
    "tropical": ("Italianno", "Italianno"),
    "lavanda": ("Parisienne", "Parisienne"),
    "areia-dourada": ("Allura", "Allura"),
    "noite-estrelada": ("Italianno", "Italianno"),
}


def apply_typography(apps, schema_editor):
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    for code, (font, query_font) in TYPOGRAPHY.items():
        InvitationTemplate.objects.filter(code=code).update(
            display_font=f'"{font}", "Segoe Script", cursive',
            body_font='"Cormorant Garamond", Georgia, serif',
            google_fonts=f"{query_font}|Cormorant+Garamond:wght@400;500;600",
        )


class Migration(migrations.Migration):
    dependencies = [("templates_manager", "0007_invitationtemplate_default_music")]
    operations = [migrations.RunPython(apply_typography, migrations.RunPython.noop)]
