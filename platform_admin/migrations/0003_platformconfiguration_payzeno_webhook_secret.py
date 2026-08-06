from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("platform_admin", "0002_platformconfiguration_payzeno_api_key_secret_and_more")]

    operations = [
        migrations.AddField(
            model_name="platformconfiguration",
            name="payzeno_webhook_secret_secret",
            field=models.TextField(blank=True, editable=False),
        ),
    ]
