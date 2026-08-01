from django.db import migrations, models


OLD_MESSAGE = (
    "Olá {nome}! 💌 É com muita alegria que partilhamos contigo o convite de {evento}. "
    "Abre o teu convite e confirma a tua presença: {link}"
)
NEW_MESSAGE = (
    "Olá {nome}! 💛 Somos {evento} e queremos muito celebrar este dia contigo. "
    "Preparámos um convite especial para ti; abre e confirma a tua presença: {link} "
    "Com carinho, {evento}."
)


def refresh_untouched_messages(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    Wedding.objects.filter(sms_invitation_message=OLD_MESSAGE).update(
        sms_invitation_message=NEW_MESSAGE
    )


class Migration(migrations.Migration):
    dependencies = [("weddings", "0008_alter_wedding_sms_invitation_message")]
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
        migrations.RunPython(refresh_untouched_messages, migrations.RunPython.noop),
    ]
