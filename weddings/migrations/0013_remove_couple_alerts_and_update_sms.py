from django.db import migrations, models


NEW_MESSAGE = (
    "*O Nosso Casamento*\n"
    "Ola {nome}! Sera uma alegria celebrar este dia contigo.\n"
    "Convite:{link}\n\n"
    "{evento}"
)


def update_sms_message(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    Wedding.objects.all().update(sms_invitation_message=NEW_MESSAGE)


class Migration(migrations.Migration):
    dependencies = [("weddings", "0012_compact_ascii_sms")]

    operations = [
        migrations.AlterField(
            model_name="wedding",
            name="sms_invitation_message",
            field=models.CharField(
                default=NEW_MESSAGE,
                help_text="Sem acentos ou emojis. Pode usar {nome}, {evento} e {link}.",
                max_length=100,
                verbose_name="mensagem do convite por SMS",
            ),
        ),
        migrations.RunPython(update_sms_message, migrations.RunPython.noop),
    ]
