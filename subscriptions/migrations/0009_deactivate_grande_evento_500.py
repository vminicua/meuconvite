from django.db import migrations


def deactivate_grande_evento(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.filter(code="grande-evento-500").update(is_active=False)


def reactivate_grande_evento(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.filter(code="grande-evento-500").update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0008_templates_and_team_for_every_plan")]

    operations = [
        migrations.RunPython(deactivate_grande_evento, reactivate_grande_evento),
    ]
