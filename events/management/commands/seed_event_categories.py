"""
Cria (ou actualiza) os tipos de evento suportados pela plataforma.

    python manage.py seed_event_categories

Cada tipo define como se chamam os protagonistas, que campos próprios são
pedidos, que momentos são criados automaticamente e que programa é
sugerido. Depois disto, a equipa MeuConvite pode ajustar tudo na
administração — e acrescentar tipos novos sem tocar no código.

É seguro correr várias vezes: identifica cada tipo pelo código e não
sobrepõe alterações feitas à mão, excepto com `--force`.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from core.schema import DRESS_CODE_CHOICES
from events.models import EventCategory

CATEGORIES: list[dict] = [
    {
        "code": "casamento",
        "name": "Casamento",
        "description": "Cerimónia religiosa, civil, copo de água e recepção.",
        "icon": "bi-suit-heart",
        "uses_two_names": True,
        "primary_label": "Nome da noiva",
        "secondary_label": "Nome do noivo",
        "names_separator": "&",
        "invitation_greeting": "têm o prazer de o convidar para celebrar o seu casamento",
        "field_schema": [
            {
                "key": "traje",
                "label": "Traje",
                "type": "choice",
                "choices": list(DRESS_CODE_CHOICES),
            },
        ],
        "default_moments": [
            {"name": "Cerimónia Religiosa", "event_type": "religious", "start_time": "09:00",
             "requires_rsvp": True},
            {"name": "Recepção", "event_type": "reception", "start_time": "19:30",
             "requires_rsvp": True, "requires_qr_code": True},
        ],
        "default_schedule": [
            {"title": "Cerimónia Religiosa", "start_time": "09:00", "icon": "bi-bank"},
            {"title": "Cerimónia Civil", "start_time": "11:30", "icon": "bi-journal-check"},
            {"title": "Copo de Água", "start_time": "15:00", "icon": "bi-cup-hot"},
            {"title": "Sessão Fotográfica", "start_time": "15:30", "icon": "bi-camera"},
            {"title": "Corte do Bolo", "start_time": "18:30", "icon": "bi-cake2"},
            {"title": "Abertura da Sala", "start_time": "19:30", "icon": "bi-music-note-beamed"},
        ],
        "display_order": 10,
    },
    {
        "code": "lobolo",
        "name": "Lobolo",
        "description": "Cerimónia tradicional entre as duas famílias.",
        "icon": "bi-people",
        "uses_two_names": True,
        "primary_label": "Família anfitriã",
        "secondary_label": "Família visitante",
        "names_separator": "e",
        "invitation_greeting": "convidam-no para a cerimónia de lobolo",
        "field_schema": [
            {"key": "porta_voz", "label": "Porta-voz da família", "type": "text"},
            {"key": "instrucoes_familia", "label": "Instruções às famílias", "type": "textarea"},
        ],
        "default_moments": [
            {"name": "Lobolo", "event_type": "lobolo", "start_time": "08:00",
             "requires_rsvp": True, "show_to_all_guests": False},
        ],
        "default_schedule": [
            {"title": "Chegada das famílias", "start_time": "08:00", "icon": "bi-people"},
            {"title": "Apresentações", "start_time": "09:00", "icon": "bi-chat-heart"},
            {"title": "Almoço", "start_time": "12:30", "icon": "bi-cup-hot"},
        ],
        "display_order": 20,
    },
    {
        "code": "aniversario",
        "name": "Aniversário",
        "description": "Festa de aniversário, de qualquer idade.",
        "icon": "bi-balloon",
        "uses_two_names": False,
        "primary_label": "Nome do aniversariante",
        "invitation_greeting": "convida-o para a sua festa de aniversário",
        "field_schema": [
            {"key": "idade", "label": "Idade a celebrar", "type": "number"},
            {"key": "tema", "label": "Tema da festa", "type": "text"},
        ],
        "default_moments": [
            {"name": "Festa", "event_type": "custom", "start_time": "15:00",
             "requires_rsvp": True},
        ],
        "default_schedule": [
            {"title": "Recepção dos convidados", "start_time": "15:00", "icon": "bi-door-open"},
            {"title": "Parabéns e corte do bolo", "start_time": "17:00", "icon": "bi-cake2"},
            {"title": "Música e dança", "start_time": "18:00", "icon": "bi-music-note-beamed"},
        ],
        "display_order": 30,
    },
    {
        "code": "batismo",
        "name": "Batismo",
        "description": "Celebração religiosa e almoço de família.",
        "icon": "bi-droplet",
        "uses_two_names": False,
        "primary_label": "Nome da criança",
        "invitation_greeting": "convidam-no para o batismo de",
        "field_schema": [
            {"key": "padrinhos", "label": "Padrinhos", "type": "text"},
            {"key": "paroquia", "label": "Paróquia", "type": "text"},
        ],
        "default_moments": [
            {"name": "Cerimónia Religiosa", "event_type": "religious", "start_time": "10:00",
             "requires_rsvp": True},
            {"name": "Almoço", "event_type": "reception", "start_time": "12:30",
             "requires_rsvp": True},
        ],
        "default_schedule": [
            {"title": "Cerimónia na igreja", "start_time": "10:00", "icon": "bi-bank"},
            {"title": "Fotografias", "start_time": "11:30", "icon": "bi-camera"},
            {"title": "Almoço", "start_time": "12:30", "icon": "bi-cup-hot"},
        ],
        "display_order": 40,
    },
    {
        "code": "formatura",
        "name": "Formatura",
        "description": "Cerimónia de graduação e jantar de curso.",
        "icon": "bi-mortarboard",
        "uses_two_names": False,
        "primary_label": "Nome do graduado",
        "invitation_greeting": "convida-o para a celebração da sua formatura",
        "field_schema": [
            {"key": "curso", "label": "Curso", "type": "text"},
            {"key": "instituicao", "label": "Instituição", "type": "text"},
        ],
        "default_moments": [
            {"name": "Cerimónia de Graduação", "event_type": "custom", "start_time": "10:00",
             "requires_rsvp": True},
            {"name": "Jantar", "event_type": "reception", "start_time": "19:00",
             "requires_rsvp": True, "requires_qr_code": True},
        ],
        "default_schedule": [
            {"title": "Cerimónia de graduação", "start_time": "10:00", "icon": "bi-mortarboard"},
            {"title": "Fotografias", "start_time": "12:00", "icon": "bi-camera"},
            {"title": "Jantar de curso", "start_time": "19:00", "icon": "bi-cup-hot"},
        ],
        "display_order": 50,
    },
    {
        "code": "cha-de-bebe",
        "name": "Chá de bebé",
        "description": "Celebração antes da chegada do bebé.",
        "icon": "bi-balloon-heart",
        "uses_two_names": False,
        "primary_label": "Nome da mãe",
        "invitation_greeting": "convida-o para o chá de bebé de",
        "field_schema": [
            {"key": "nome_bebe", "label": "Nome do bebé", "type": "text"},
        ],
        "default_moments": [
            {"name": "Chá de bebé", "event_type": "custom", "start_time": "15:00",
             "requires_rsvp": True},
        ],
        "default_schedule": [
            {"title": "Recepção", "start_time": "15:00", "icon": "bi-door-open"},
            {"title": "Jogos", "start_time": "16:00", "icon": "bi-dice-5"},
            {"title": "Abertura dos presentes", "start_time": "17:00", "icon": "bi-gift"},
        ],
        "display_order": 60,
    },
    {
        "code": "evento-corporativo",
        "name": "Evento corporativo",
        "description": "Conferências, lançamentos, jantares de empresa.",
        "icon": "bi-briefcase",
        "uses_two_names": False,
        "primary_label": "Nome do evento",
        "invitation_greeting": "tem o prazer de o convidar para",
        "field_schema": [
            {"key": "organizacao", "label": "Organização", "type": "text"},
            {"key": "orador", "label": "Orador principal", "type": "text"},
            {
                "key": "codigo_vestuario",
                "label": "Código de vestuário",
                "type": "choice",
                "choices": list(DRESS_CODE_CHOICES),
            },
        ],
        "default_moments": [
            {"name": "Sessão de abertura", "event_type": "custom", "start_time": "09:00",
             "requires_rsvp": True, "requires_qr_code": True},
        ],
        "default_schedule": [
            {"title": "Registo dos participantes", "start_time": "08:30", "icon": "bi-person-badge"},
            {"title": "Sessão de abertura", "start_time": "09:00", "icon": "bi-mic"},
            {"title": "Intervalo", "start_time": "10:30", "icon": "bi-cup-hot"},
            {"title": "Encerramento", "start_time": "16:00", "icon": "bi-flag"},
        ],
        "display_order": 70,
    },
    {
        "code": "outro",
        "name": "Outro evento",
        "description": "Qualquer outra celebração, com os campos que quiser.",
        "icon": "bi-calendar-heart",
        "uses_two_names": False,
        "primary_label": "Nome do evento",
        "invitation_greeting": "convida-o para",
        "field_schema": [],
        "default_moments": [
            {"name": "Evento", "event_type": "custom", "requires_rsvp": True},
        ],
        "default_schedule": [],
        "display_order": 99,
    },
]


class Command(BaseCommand):
    help = "Cria ou actualiza os tipos de evento (casamento, aniversário, lobolo, …)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sobrepõe os tipos já existentes com os valores predefinidos.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        force = options["force"]
        created_count = 0
        updated_count = 0

        for definition in CATEGORIES:
            data = dict(definition)
            code = data.pop("code")

            category, created = EventCategory.objects.get_or_create(code=code, defaults=data)
            if created:
                created_count += 1
                self.stdout.write(f"  criado: {category.name}")
                continue

            if not force:
                continue

            for field, value in data.items():
                setattr(category, field, value)
            category.full_clean()
            category.save()
            updated_count += 1
            self.stdout.write(f"  actualizado: {category.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Tipos de evento prontos: {created_count} criado(s), "
                f"{updated_count} actualizado(s), {EventCategory.objects.count()} no total."
            )
        )
        if not force and created_count == 0 and updated_count == 0:
            self.stdout.write(
                "Nada mudou. Use --force para repor os valores predefinidos."
            )
