from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("weddings", "0017_musictrack_wedding_invitation_track_and_more")]

    operations = [
        migrations.AddField(
            model_name="wedding",
            name="invitation_host",
            field=models.CharField(
                choices=[
                    ("couple", "Os noivos convidam"),
                    ("parents", "Os pais de ambos convidam"),
                ],
                default="couple",
                max_length=20,
                verbose_name="quem convida",
            ),
        ),
        migrations.AddField(
            model_name="wedding",
            name="primary_parents_names",
            field=models.CharField(
                blank=True,
                help_text="Ex.: Maria e Joaquim Mate",
                max_length=250,
                verbose_name="pais da noiva",
            ),
        ),
        migrations.AddField(
            model_name="wedding",
            name="secondary_parents_names",
            field=models.CharField(
                blank=True,
                help_text="Ex.: Ana e Manuel Cossa",
                max_length=250,
                verbose_name="pais do noivo",
            ),
        ),
    ]
