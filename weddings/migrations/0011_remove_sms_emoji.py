from django.db import migrations, models


OLD_MESSAGE = (
    "Olá {nome}! 💛 Somos {evento} e queremos muito celebrar este dia contigo. "
    "Preparámos um convite especial para ti; abre e confirma a tua presença: {link} "
    "Com carinho, {evento}."
)
NEW_MESSAGE = (
    "Olá {nome}! Somos {evento} e queremos muito celebrar este dia contigo. "
    "Preparámos um convite especial para ti; abre e confirma a tua presença: {link} "
    "Com carinho, {evento}."
)


def remove_emoji_from_default_messages(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    Wedding.objects.filter(sms_invitation_message=OLD_MESSAGE).update(
        sms_invitation_message=NEW_MESSAGE
    )


class Migration(migrations.Migration):
    dependencies = [("weddings", "0010_wedding_notification_phones")]
    operations = [
        migrations.AlterField(
            model_name="wedding",
            name="sms_invitation_message",
            field=models.CharField(
                default=NEW_MESSAGE,
                help_text="Pode usar {nome}, {evento} e {link}.",
                max_length=500,
                verbose_name="mensagem do convite por SMS",
            ),
        ),
        migrations.RunPython(remove_emoji_from_default_messages, migrations.RunPython.noop),
    ]
