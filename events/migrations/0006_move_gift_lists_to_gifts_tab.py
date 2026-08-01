from django.db import migrations


def remove_legacy_gift_field(apps, schema_editor):
    EventCategory = apps.get_model("events", "EventCategory")
    for category in EventCategory.objects.all():
        schema = category.field_schema or []
        cleaned = [field for field in schema if field.get("key") != "lista_presentes"]
        if cleaned != schema:
            category.field_schema = cleaned
            category.save(update_fields=["field_schema", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("events", "0005_unify_programme")]
    operations = [migrations.RunPython(remove_legacy_gift_field, migrations.RunPython.noop)]
