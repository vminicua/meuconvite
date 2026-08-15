from django.db import migrations, models


def enable_seating(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.update(allows_seating=True)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0011_event_specific_plan_catalogue")]

    operations = [
        migrations.RunPython(enable_seating, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="plan",
            name="allows_seating",
            field=models.BooleanField(default=True, verbose_name="gestão de mesas"),
        ),
    ]
