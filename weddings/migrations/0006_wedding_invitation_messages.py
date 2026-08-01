from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("weddings", "0005_optional_address_and_event_attributes"),
    ]

    operations = [
        migrations.AddField(
            model_name="wedding",
            name="cover_message",
            field=models.CharField(
                blank=True,
                help_text="Frase curta apresentada antes de abrir o convite.",
                max_length=200,
                verbose_name="mensagem da capa",
            ),
        ),
        migrations.AddField(
            model_name="wedding",
            name="invitation_message",
            field=models.TextField(
                blank=True,
                help_text="Mensagem apresentada ao convidado depois de abrir o convite.",
                max_length=1000,
                verbose_name="mensagem principal do convite",
            ),
        ),
    ]
