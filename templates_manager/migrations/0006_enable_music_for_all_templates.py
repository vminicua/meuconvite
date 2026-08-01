from django.db import migrations


def enable_music(apps, schema_editor):
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    InvitationTemplate.objects.update(supports_music=True)


class Migration(migrations.Migration):
    dependencies = [("templates_manager", "0005_refine_template_typography")]
    operations = [migrations.RunPython(enable_music, migrations.RunPython.noop)]
