from django.db import migrations


CORPORATE_FIELDS = [
    {"key": "organizacao", "label": "Organização anfitriã", "type": "text", "required": True},
    {"key": "tipo_evento_corporativo", "label": "Formato do evento", "type": "choice", "required": True, "choices": ["Conferência", "Seminário", "Workshop", "Lançamento", "Networking", "Gala corporativa", "Team building", "Outro"]},
    {"key": "modalidade", "label": "Modalidade", "type": "choice", "required": True, "choices": ["Presencial", "Híbrido", "Online"]},
    {"key": "publico_alvo", "label": "Público-alvo", "type": "text"},
    {"key": "tema_objetivo", "label": "Tema ou objetivo", "type": "textarea"},
    {"key": "orador", "label": "Orador principal", "type": "text"},
    {"key": "contacto_evento", "label": "Contacto do evento", "type": "text"},
    {"key": "link_registo", "label": "Ligação de registo ou transmissão", "type": "url"},
    {"key": "patrocinadores", "label": "Parceiros ou patrocinadores", "type": "list"},
    {"key": "codigo_vestuario", "label": "Código de vestuário", "type": "choice", "choices": ["Traje de gala", "Traje formal", "Traje semi-formal", "Traje tradicional", "Traje casual", "Traje temático"]},
]


def forwards(apps, schema_editor):
    EventCategory = apps.get_model("events", "EventCategory")
    EventCategory.objects.update_or_create(
        code="evento-corporativo",
        defaults={
            "name": "Evento corporativo",
            "description": "Conferências, lançamentos, jantares de empresa.",
            "icon": "bi-briefcase",
            "uses_two_names": False,
            "primary_label": "Nome do evento",
            "secondary_label": "",
            "names_separator": "&",
            "invitation_greeting": "tem o prazer de o convidar para este evento corporativo",
            "field_schema": CORPORATE_FIELDS,
            "default_moments": [{"name": "Sessão de abertura", "event_type": "custom", "start_time": "09:00", "requires_rsvp": True, "requires_qr_code": True}],
            "default_schedule": [
                {"title": "Registo dos participantes", "start_time": "08:30", "icon": "bi-person-badge"},
                {"title": "Sessão de abertura", "start_time": "09:00", "icon": "bi-mic"},
                {"title": "Painel principal", "start_time": "09:30", "icon": "bi-people"},
                {"title": "Intervalo", "start_time": "10:30", "icon": "bi-cup-hot"},
                {"title": "Sessões e networking", "start_time": "11:00", "icon": "bi-diagram-3"},
                {"title": "Encerramento", "start_time": "16:00", "icon": "bi-flag"},
            ],
            "is_active": True,
            "display_order": 70,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("events", "0007_rename_formatura_display_to_graduacao")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
