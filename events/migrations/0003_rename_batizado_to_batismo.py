"""
Em Moçambique diz-se «batismo», não «batizado».

O tipo de evento já tinha sido criado com o nome antigo, por isso não
basta corrigir o comando `seed_event_categories`: a linha existente
também tem de ser actualizada. Só são tocados os campos com a palavra
errada — descrição, campos próprios e programa ficam como estão, tal como
qualquer alteração que a equipa já tenha feito na administração.
"""

from __future__ import annotations

from django.db import migrations

OLD_CODE = "batizado"
NEW_CODE = "batismo"

RENAMES = {
    "name": ("Batizado", "Batismo"),
    "invitation_greeting": ("convidam-no para o batizado de", "convidam-no para o batismo de"),
}


def _rename(apps, old_code: str, new_code: str, index: int) -> None:
    EventCategory = apps.get_model("events", "EventCategory")

    category = EventCategory.objects.filter(code=old_code).first()
    if category is None:
        return

    # Se o código de destino já existir (por exemplo, o comando de seed
    # correu depois da correcção), não há nada a fazer aqui.
    if EventCategory.objects.filter(code=new_code).exclude(pk=category.pk).exists():
        return

    category.code = new_code
    for field, values in RENAMES.items():
        current = getattr(category, field, "")
        if current == values[index]:
            setattr(category, field, values[1 - index])
    category.save(update_fields=["code", *RENAMES, "updated_at"])


def forwards(apps, schema_editor) -> None:
    _rename(apps, OLD_CODE, NEW_CODE, index=0)


def backwards(apps, schema_editor) -> None:
    _rename(apps, NEW_CODE, OLD_CODE, index=1)


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0002_eventcategory_scheduleitem_extra_data"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
