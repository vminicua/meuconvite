from django.db import migrations, models


DRESS_CHOICES = [
    "Traje de gala",
    "Traje formal",
    "Traje semi-formal",
    "Traje tradicional",
    "Traje casual",
    "Traje temático",
]


def _replace_fields(schema, replacements):
    result = []
    found = set()
    for definition in schema or []:
        if not isinstance(definition, dict):
            continue
        key = definition.get("key")
        if key in replacements:
            result.append(replacements[key])
            found.add(key)
        else:
            result.append(definition)
    for key, definition in replacements.items():
        if key not in found:
            result.append(definition)
    return result


def forwards(apps, schema_editor):
    EventCategory = apps.get_model("events", "EventCategory")
    Wedding = apps.get_model("weddings", "Wedding")

    dress = {
        "key": "traje",
        "label": "Traje",
        "type": "choice",
        "choices": DRESS_CHOICES,
    }
    gifts = {
        "key": "lista_presentes",
        "label": "Lista de presentes",
        "type": "list",
        "placeholder": "Ex.: Liquidificador ou ligação para a loja",
        "help_text": "Adicione um presente ou ligação por linha.",
    }

    wedding_category = EventCategory.objects.filter(code="casamento").first()
    if wedding_category:
        wedding_category.field_schema = _replace_fields(
            wedding_category.field_schema,
            {"traje": dress, "lista_presentes": gifts},
        )
        wedding_category.save(update_fields=["field_schema", "updated_at"])

    baby_category = EventCategory.objects.filter(code="cha-de-bebe").first()
    if baby_category:
        baby_gifts = dict(gifts)
        baby_gifts["placeholder"] = "Ex.: Fraldas tamanho 2 ou ligação para a loja"
        baby_category.field_schema = _replace_fields(
            baby_category.field_schema,
            {"lista_presentes": baby_gifts},
        )
        baby_category.save(update_fields=["field_schema", "updated_at"])

    corporate = EventCategory.objects.filter(code="evento-corporativo").first()
    if corporate:
        corporate.field_schema = _replace_fields(
            corporate.field_schema,
            {
                "codigo_vestuario": {
                    "key": "codigo_vestuario",
                    "label": "Código de vestuário",
                    "type": "choice",
                    "choices": DRESS_CHOICES,
                }
            },
        )
        corporate.save(update_fields=["field_schema", "updated_at"])

    for wedding in Wedding.objects.exclude(extra_data={}):
        data = dict(wedding.extra_data or {})
        gifts_value = data.get("lista_presentes")
        if isinstance(gifts_value, str) and gifts_value.strip():
            data["lista_presentes"] = [gifts_value.strip()]
            wedding.extra_data = data
            wedding.save(update_fields=["extra_data", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0004_alter_scheduleitem_wedding_and_more"),
        ("weddings", "0004_alter_wedding_selected_template"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wedding",
            name="city",
            field=models.CharField(
                blank=True,
                default="",
                max_length=250,
                verbose_name="endereço",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
