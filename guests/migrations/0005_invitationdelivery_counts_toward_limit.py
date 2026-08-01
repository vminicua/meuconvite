from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("guests", "0004_gift_giftselection_gift_gift_wedding_active_idx_and_more")]

    operations = [
        migrations.AddField(
            model_name="invitationdelivery",
            name="counts_toward_limit",
            field=models.BooleanField(
                default=True,
                help_text="Desmarcado para notificações operacionais e reposições de saldo.",
                verbose_name="conta para o limite",
            ),
        ),
    ]
