from django.db import migrations


def require_covers(apps, schema_editor):
    InvitationTemplate = apps.get_model("templates_manager", "InvitationTemplate")
    InvitationTemplate.objects.filter(has_cover=False).update(has_cover=True)


class Migration(migrations.Migration):
    dependencies = [("templates_manager", "0003_template_cover_image")]
    operations = [migrations.RunPython(require_covers, migrations.RunPython.noop)]
