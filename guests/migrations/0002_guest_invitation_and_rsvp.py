from django.db import migrations, models
import core.utils


def populate_tokens(apps, schema_editor):
    Guest = apps.get_model("guests", "Guest")
    for guest in Guest.objects.filter(invitation_token__isnull=True).iterator():
        guest.invitation_token = core.utils.generate_secure_token()
        guest.save(update_fields=["invitation_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0005_unify_programme"),
        ("guests", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="guest",
            name="invitation_token",
            field=models.CharField(editable=False, max_length=64, null=True, verbose_name="token do convite"),
        ),
        migrations.RunPython(populate_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="guest",
            name="invitation_token",
            field=models.CharField(default=core.utils.generate_secure_token, editable=False, max_length=64, unique=True, verbose_name="token do convite"),
        ),
        migrations.AddField(
            model_name="guest",
            name="rsvp_status",
            field=models.CharField(choices=[("pending", "Por responder"), ("confirmed", "Confirmado"), ("declined", "Não vai comparecer")], db_index=True, default="pending", max_length=20, verbose_name="confirmação"),
        ),
        migrations.AddField(
            model_name="guest",
            name="responded_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="respondido em"),
        ),
        migrations.AddField(
            model_name="guest",
            name="allowed_events",
            field=models.ManyToManyField(blank=True, help_text="Sem selecção, o convidado recebe acesso a todo o programa público.", related_name="invited_guests", to="events.weddingevent", verbose_name="programa autorizado"),
        ),
    ]
