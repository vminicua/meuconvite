import core.storage
import core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("templates_manager", "0002_seed_templates"),
    ]

    operations = [
        migrations.RenameField(
            model_name="invitationtemplate",
            old_name="preview_image",
            new_name="cover_image",
        ),
        migrations.AlterField(
            model_name="invitationtemplate",
            name="cover_image",
            field=models.ImageField(
                blank=True,
                help_text=(
                    "Imagem vertical usada no catálogo. Recomendado: proporção 4:5, "
                    "mínimo 1200 × 1500 px, JPG, PNG ou WEBP até 5 MB."
                ),
                null=True,
                upload_to=core.storage.template_cover_upload_to,
                validators=[core.validators.validate_image_upload],
                verbose_name="cover do template",
            ),
        ),
    ]
