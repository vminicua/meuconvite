from django.db import migrations


SCHEMAS = {
    "lobolo": [
        {"key": "porta_voz", "label": "Porta-voz da família", "type": "text"},
        {"key": "instrucoes_familia", "label": "Instruções às famílias", "type": "textarea"},
        {"key": "traje_tradicional", "label": "Traje ou orientação tradicional", "type": "text"},
    ],
    "aniversario": [
        {"key": "idade", "label": "Idade a celebrar", "type": "number"},
        {"key": "tema", "label": "Tema da festa", "type": "text"},
        {"key": "traje", "label": "Traje", "type": "choice", "choices": ["Formal", "Semi-formal", "Casual elegante", "Tradicional", "Branco", "Preto", "Livre"]},
    ],
    "batismo": [
        {"key": "padrinhos", "label": "Padrinhos", "type": "text"},
        {"key": "paroquia", "label": "Paróquia", "type": "text"},
        {"key": "celebrante", "label": "Celebrante", "type": "text"},
    ],
    "formatura": [
        {"key": "curso", "label": "Curso", "type": "text"},
        {"key": "instituicao", "label": "Instituição", "type": "text"},
        {"key": "qualificacao", "label": "Grau ou qualificação", "type": "text"},
    ],
    "cha-de-bebe": [
        {"key": "nome_bebe", "label": "Nome do bebé", "type": "text"},
        {"key": "previsao_nascimento", "label": "Previsão de nascimento", "type": "date"},
        {"key": "tema", "label": "Tema ou paleta", "type": "text"},
    ],
    "outro": [
        {"key": "tipo_evento", "label": "Tipo de evento", "type": "text", "required": True},
        {"key": "anfitriao", "label": "Anfitrião ou organização", "type": "text"},
        {"key": "tema", "label": "Tema ou objetivo", "type": "textarea"},
        {"key": "traje", "label": "Traje", "type": "choice", "choices": ["Formal", "Semi-formal", "Casual elegante", "Tradicional", "Branco", "Preto", "Livre"]},
    ],
}

def forwards(apps, schema_editor):
    Category = apps.get_model("events", "EventCategory")
    Category.objects.filter(code="casamento").update(display_order=10)
    Category.objects.filter(code="evento-corporativo").update(display_order=15)
    for code, schema in SCHEMAS.items():
        Category.objects.filter(code=code).update(field_schema=schema)


class Migration(migrations.Migration):
    dependencies = [("events", "0008_refine_corporate_category")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
