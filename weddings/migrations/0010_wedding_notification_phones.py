from django.db import migrations, models
import core.validators


class Migration(migrations.Migration):
    dependencies = [("weddings", "0009_beautiful_couple_sms")]
    operations = [
        migrations.AddField(
            model_name="wedding",
            name="notification_phone_primary",
            field=models.CharField(
                blank=True,
                help_text="Recebe SMS quando um convidado responde ou escolhe um presente.",
                max_length=20,
                validators=[core.validators.validate_phone],
                verbose_name="telefone para notificações",
            ),
        ),
        migrations.AddField(
            model_name="wedding",
            name="notification_phone_secondary",
            field=models.CharField(
                blank=True,
                help_text="Opcional. Pode ser o telefone do outro noivo ou anfitrião.",
                max_length=20,
                validators=[core.validators.validate_phone],
                verbose_name="segundo telefone",
            ),
        ),
    ]
