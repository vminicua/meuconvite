from django.db import migrations


ENGAGEMENT_CODES = [
    "noivado-pedido-de-ouro",
    "noivado-jardim-promessas",
    "noivado-safira-eterna",
    "noivado-rose-contemporaneo",
    "noivado-noite-veludo",
    "noivado-marfim-minimalista",
    "noivado-capulana-amor",
]


def forwards(apps, schema_editor):
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    for template in Template.objects.filter(code__in=ENGAGEMENT_CODES):
        families = [part for part in template.google_fonts.split("|") if part]
        if "Great+Vibes" not in families:
            families.insert(0, "Great+Vibes")
        template.display_font = '"Great Vibes", "Segoe Script", cursive'
        template.google_fonts = "|".join(families)
        template.save(update_fields=["display_font", "google_fonts", "updated_at"])


def backwards(apps, schema_editor):
    Template = apps.get_model("templates_manager", "InvitationTemplate")
    Template.objects.filter(code__in=ENGAGEMENT_CODES).update(
        display_font='"Playfair Display", Georgia, serif'
    )


class Migration(migrations.Migration):
    dependencies = [("templates_manager", "0011_engagement_collection")]
    operations = [migrations.RunPython(forwards, backwards)]
