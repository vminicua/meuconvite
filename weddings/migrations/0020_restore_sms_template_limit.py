from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("weddings", "0019_expand_sms_template_limit")]

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
                max_length=100,
                verbose_name="mensagem do convite por SMS",
            ),
        ),
    ]
