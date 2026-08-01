from django.db import migrations, models


def enable_music(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    Wedding.objects.all().update(show_music=True)


class Migration(migrations.Migration):
    dependencies = [("weddings", "0013_remove_couple_alerts_and_update_sms")]

    operations = [
        migrations.AlterField(
            model_name="wedding",
            name="show_music",
            field=models.BooleanField(default=True, verbose_name="reproduzir música"),
        ),
        migrations.RunPython(enable_music, migrations.RunPython.noop),
    ]
