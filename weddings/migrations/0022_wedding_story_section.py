from django.db import migrations, models


def preserve_existing_stories(apps, schema_editor):
    Wedding = apps.get_model("weddings", "Wedding")
    Wedding.objects.exclude(story="").update(show_story=True)


class Migration(migrations.Migration):
    dependencies = [("weddings", "0021_publish_events_by_default")]
    operations = [
        migrations.AddField(
            model_name="wedding",
            name="show_story",
            field=models.BooleanField(default=False, help_text="Apresenta esta secção no convite público.", verbose_name="mostrar a nossa história"),
        ),
        migrations.AddField(
            model_name="wedding",
            name="story_title",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="título da história"),
        ),
        migrations.AddField(
            model_name="wedding",
            name="story_verse",
            field=models.TextField(blank=True, max_length=700, verbose_name="versículo ou citação"),
        ),
        migrations.AddField(
            model_name="wedding",
            name="story_verse_reference",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="referência do versículo"),
        ),
        migrations.RunPython(preserve_existing_stories, migrations.RunPython.noop),
    ]
