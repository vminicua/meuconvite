from django.db import migrations, models

import core.storage
import core.validators


class Migration(migrations.Migration):
    dependencies = [("templates_manager", "0006_enable_music_for_all_templates")]

    operations = [
        migrations.AddField(
            model_name="invitationtemplate",
            name="default_music",
            field=models.FileField(
                blank=True,
                help_text=(
                    "Opcional. Quando vazio, usa a música padrão da plataforma. "
                    "MP3, M4A ou OGG até 8 MB."
                ),
                null=True,
                upload_to=core.storage.template_music_upload_to,
                validators=[core.validators.validate_audio_upload],
                verbose_name="música do template",
            ),
        ),
    ]
