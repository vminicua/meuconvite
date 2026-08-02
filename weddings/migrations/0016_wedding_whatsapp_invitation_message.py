from django.db import migrations, models


DEFAULT_WHATSAPP_INVITATION_MESSAGE = (
    "Olá, {nome}!\n\n"
    "É com muita alegria que te convidamos a celebrar connosco este momento especial.\n\n"
    "Preparámos um convite especial para ti. Abre o link abaixo e confirma a tua presença:\n\n"
    "{link}\n\n"
    "Com carinho,\n{evento}"
)


class Migration(migrations.Migration):
    dependencies = [("weddings", "0015_weddinggalleryphoto")]

    operations = [
        migrations.AddField(
            model_name="wedding",
            name="whatsapp_invitation_message",
            field=models.TextField(
                default=DEFAULT_WHATSAPP_INVITATION_MESSAGE,
                help_text="Pode usar {nome}, {evento} e {link}.",
                max_length=1000,
                verbose_name="mensagem do convite por WhatsApp",
            ),
        ),
    ]
