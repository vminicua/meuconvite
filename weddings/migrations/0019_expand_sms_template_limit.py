from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("weddings", "0018_wedding_invitation_hosts")]

    operations = [
        migrations.AlterField(
            model_name="wedding",
            name="sms_invitation_message",
            field=models.CharField(
                default=(
                    "*O Nosso Casamento*\n"
                    "Ola {nome}! Sera uma alegria celebrar este dia contigo.\n"
                    "Convite:{link}\n\n"
                    "{evento}"
                ),
                help_text="Sem acentos ou emojis. Pode usar {nome}, {evento} e {link}.",
                max_length=160,
                verbose_name="mensagem do convite por SMS",
            ),
        ),
    ]
