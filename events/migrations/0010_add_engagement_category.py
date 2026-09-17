from django.db import migrations


ENGAGEMENT = {
    "name": "Noivado",
    "description": "Celebração do pedido e da promessa de uma vida a dois.",
    "icon": "bi-gem",
    "uses_two_names": True,
    "primary_label": "Nome da noiva",
    "secondary_label": "Nome do noivo",
    "names_separator": "&",
    "invitation_greeting": "têm o prazer de o convidar para celebrar o seu noivado",
    "field_schema": [
        {"key": "traje", "label": "Traje", "type": "choice", "choices": ["Traje de gala", "Traje formal", "Traje semi-formal", "Traje tradicional", "Traje casual", "Traje temático"]},
        {"key": "surpresa", "label": "O pedido é surpresa?", "type": "boolean"},
    ],
    "default_moments": [
        {"name": "Celebração do Noivado", "event_type": "reception", "start_time": "17:00", "requires_rsvp": True},
    ],
    "default_schedule": [
        {"title": "Recepção dos convidados", "start_time": "17:00", "icon": "bi-stars"},
        {"title": "O pedido e o brinde", "start_time": "18:00", "icon": "bi-gem"},
        {"title": "Jantar e celebração", "start_time": "19:00", "icon": "bi-cup-straw"},
        {"title": "Fotografias", "start_time": "20:00", "icon": "bi-camera"},
    ],
    "is_active": True,
    "display_order": 12,
}


def forwards(apps, schema_editor):
    Category = apps.get_model("events", "EventCategory")
    Category.objects.update_or_create(code="noivado", defaults=ENGAGEMENT)


def backwards(apps, schema_editor):
    Category = apps.get_model("events", "EventCategory")
    Category.objects.filter(code="noivado").delete()


class Migration(migrations.Migration):
    # Keep the legacy template categorisation ahead of the new category on
    # fresh databases. Otherwise migration 0009 would mistake Noivado for an
    # existing catch-all social category and attach every wedding template.
    dependencies = [
        ("events", "0009_category_specific_fields_and_order"),
        ("templates_manager", "0010_category_template_collections"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
