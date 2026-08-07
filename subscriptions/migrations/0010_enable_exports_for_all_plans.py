from django.db import migrations, models


def enable_exports(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Plan.objects.update(allows_exports=True)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0009_deactivate_grande_evento_500")]

    operations = [
        migrations.AlterField(
            model_name="plan",
            name="allows_exports",
            field=models.BooleanField(default=True, verbose_name="exportações"),
        ),
        migrations.RunPython(enable_exports, migrations.RunPython.noop),
    ]
