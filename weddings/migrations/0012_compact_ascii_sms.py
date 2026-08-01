from django.db import migrations, models


NEW_MESSAGE = "Ola {nome}! Somos {evento}. Preparamos este convite para ti: {link}"


def replace_existing_messages(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    # Existing free-form messages may contain Unicode or expand to several
    # paid segments. Replace them so deployment is safe immediately.
    Wedding.objects.all().update(sms_invitation_message=NEW_MESSAGE)


class Migration(migrations.Migration):
    dependencies = [("weddings", "0011_remove_sms_emoji")]

    operations = [
        migrations.RunPython(replace_existing_messages, migrations.RunPython.noop),
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
    ]
