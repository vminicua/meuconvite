from django.db import migrations


def use_mozambican_graduation_name(apps, schema_editor):
    EventCategory = apps.get_model("events", "EventCategory")
    EventCategory.objects.filter(code="formatura").update(
        name="Graduação",
        description="Cerimónia de graduação e jantar de curso.",
        invitation_greeting="convida-o para a celebração da sua graduação",
    )


class Migration(migrations.Migration):
    dependencies = [("events", "0006_move_gift_lists_to_gifts_tab")]
    operations = [
        migrations.RunPython(use_mozambican_graduation_name, migrations.RunPython.noop),
    ]
