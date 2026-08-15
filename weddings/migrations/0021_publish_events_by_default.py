from django.db import migrations, models
from django.utils import timezone


def publish_drafts(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    Wedding.objects.filter(status="draft").update(
        status="published",
        published_at=timezone.now(),
    )


class Migration(migrations.Migration):
    dependencies = [("weddings", "0020_restore_sms_template_limit")]

    operations = [
        migrations.RunPython(publish_drafts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="wedding",
            name="status",
            field=models.CharField(
                choices=[
                    ("published", "Publicado"),
                    ("archived", "Arquivado"),
                    ("blocked", "Bloqueado"),
                ],
                db_index=True,
                default="published",
                max_length=20,
                verbose_name="estado",
            ),
        ),
    ]
