from django.db import migrations


def make_universal(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.update(templates_limit=0, allows_team=True)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0007_one_free_event_and_qr_for_all")]
    operations = [migrations.RunPython(make_universal, migrations.RunPython.noop)]
