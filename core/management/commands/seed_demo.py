"""
Creates a demonstration wedding with fictional data.

Everything is invented: no real person's data is used. The command is
refused in production unless `--force` is given, and it never touches
existing records other than the demo ones it owns.

    python manage.py seed_demo
    python manage.py seed_demo --reset

Guests, invitations, RSVPs, tables, QR codes and check-ins are added to
this command as their applications are implemented (phases 2 and 3).
"""

from __future__ import annotations

from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from events.models import EventType, ScheduleItem, WeddingEvent, WeddingLocation
from weddings.models import Wedding, WeddingMember, WeddingRole

User = get_user_model()

DEMO_OWNER_EMAIL = "demo.noivos@meuconvite.example"
DEMO_PLANNER_EMAIL = "demo.planner@meuconvite.example"
DEMO_PASSWORD_ENV = "DEMO_USER_PASSWORD"


class Command(BaseCommand):
    help = "Cria um casamento de demonstração com dados fictícios."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove o casamento de demonstração existente antes de criar um novo.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite executar mesmo com DEBUG=False (use com cuidado).",
        )

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "Este comando cria dados fictícios e está bloqueado fora do ambiente de "
                "desenvolvimento. Use --force se tiver a certeza."
            )

        password = self._get_password()

        with transaction.atomic():
            owner = self._get_or_create_user(
                DEMO_OWNER_EMAIL, "Natércia", "Matola", password
            )
            planner = self._get_or_create_user(
                DEMO_PLANNER_EMAIL, "Maria", "Bila", password
            )

            if options["reset"]:
                deleted, _ = Wedding.objects.filter(owner=owner).delete()
                if deleted:
                    self.stdout.write(f"Casamento de demonstração anterior removido ({deleted} registos).")

            if Wedding.objects.filter(owner=owner).exists():
                raise CommandError(
                    "Já existe um casamento de demonstração. Use --reset para o substituir."
                )

            wedding = self._create_wedding(owner)
            self._add_planner(wedding, planner)
            locations = self._create_locations(wedding)
            events = self._create_events(wedding, locations)
            self._create_schedule(wedding, events, locations)

        self.stdout.write(self.style.SUCCESS("Dados de demonstração criados."))
        self.stdout.write(f"  Casamento : {wedding.couple_names} ({wedding.main_date:%d/%m/%Y})")
        self.stdout.write(f"  Painel    : /casamentos/{wedding.pk}/")
        self.stdout.write(f"  Noivos    : {DEMO_OWNER_EMAIL}")
        self.stdout.write(f"  Planner   : {DEMO_PLANNER_EMAIL}")
        self.stdout.write(
            "  Palavra-passe: definida em "
            f"{DEMO_PASSWORD_ENV} (não é escrita nos registos nem no código)."
        )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _get_password(self) -> str:
        import os

        password = os.environ.get(DEMO_PASSWORD_ENV, "")
        if not password:
            from django.utils.crypto import get_random_string

            password = get_random_string(16)
            self.stdout.write(
                self.style.WARNING(
                    f"{DEMO_PASSWORD_ENV} não está definida: foi gerada uma palavra-passe "
                    "aleatória. Defina a variável de ambiente para poder iniciar sessão "
                    "com as contas de demonstração."
                )
            )
        return password

    def _get_or_create_user(self, email: str, first: str, last: str, password: str):
        from allauth.account.models import EmailAddress

        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first,
                last_name=last,
                is_email_verified=True,
            )
            EmailAddress.objects.get_or_create(
                user=user, email=email, defaults={"verified": True, "primary": True}
            )
            self.stdout.write(f"Utilizador criado: {email}")
        return user

    def _create_wedding(self, owner) -> Wedding:
        main_date = timezone.localdate() + timedelta(days=90)
        wedding = Wedding.objects.create(
            owner=owner,
            bride_full_name="Natércia Alice Matola",
            groom_full_name="Hivaldo José Cossa",
            bride_short_name="Natércia",
            groom_short_name="Hivaldo",
            main_date=main_date,
            city="Maputo",
            country="Moçambique",
            welcome_message=(
                "É com muita alegria que vos convidamos para celebrar connosco "
                "este dia tão especial."
            ),
            story=(
                "Conhecemo-nos em Maputo, numa tarde de Novembro, e desde então "
                "não nos largámos mais."
            ),
            hashtag="#NaterciaEHivaldo2026",
            rsvp_deadline=main_date - timedelta(days=21),
        )
        membership = WeddingMember(
            wedding=wedding,
            user=owner,
            role=WeddingRole.OWNER,
            accepted_at=timezone.now(),
        )
        membership.apply_role_defaults()
        membership.save()
        return wedding

    def _add_planner(self, wedding: Wedding, planner) -> None:
        membership = WeddingMember(
            wedding=wedding,
            user=planner,
            role=WeddingRole.WEDDING_PLANNER,
            accepted_at=timezone.now(),
            notes="Conta de demonstração da wedding planner.",
        )
        membership.apply_role_defaults()
        membership.save()

    def _create_locations(self, wedding: Wedding) -> dict[str, WeddingLocation]:
        church = WeddingLocation.objects.create(
            wedding=wedding,
            name="Igreja de Santo António da Polana",
            address="Av. Julius Nyerere, Maputo",
            description="Entrada principal pelo portão lateral.",
            contact_phone="+258841112233",
            parking_information="Estacionamento gratuito em frente à igreja.",
            display_order=10,
        )
        hall = WeddingLocation.objects.create(
            wedding=wedding,
            name="Salão Vila Sol",
            address="Av. Marginal, Maputo",
            description="Recepção e copo de água.",
            contact_phone="+258842223344",
            transport_information="Autocarro disponível a partir da igreja às 14h00.",
            display_order=20,
        )
        family_house = WeddingLocation.objects.create(
            wedding=wedding,
            name="Casa da família Matola",
            address="Bairro da Malhangalene, Maputo",
            description="Cerimónias tradicionais com a família.",
            display_order=30,
        )
        return {"church": church, "hall": hall, "family": family_house}

    def _create_events(self, wedding: Wedding, locations: dict) -> dict[str, WeddingEvent]:
        main_date: date = wedding.main_date

        lobolo = WeddingEvent.objects.create(
            wedding=wedding,
            event_type=EventType.LOBOLO,
            name="Lobolo",
            description="Cerimónia tradicional entre as duas famílias.",
            date=main_date - timedelta(days=30),
            start_time=time(8, 0),
            end_time=time(13, 0),
            location=locations["family"],
            host_family="Família Matola",
            dress_code="Traje tradicional",
            requires_rsvp=True,
            show_to_all_guests=False,
            display_order=10,
        )
        religious = WeddingEvent.objects.create(
            wedding=wedding,
            event_type=EventType.RELIGIOUS,
            name="Cerimónia Religiosa",
            description="Celebração religiosa do matrimónio.",
            date=main_date,
            start_time=time(9, 0),
            end_time=time(11, 0),
            location=locations["church"],
            dress_code="Traje formal",
            requires_rsvp=True,
            requires_qr_code=False,
            display_order=20,
        )
        civil = WeddingEvent.objects.create(
            wedding=wedding,
            event_type=EventType.CIVIL,
            name="Cerimónia Civil",
            date=main_date,
            start_time=time(11, 30),
            end_time=time(12, 30),
            location=locations["church"],
            requires_rsvp=True,
            display_order=30,
        )
        welcome_drink = WeddingEvent.objects.create(
            wedding=wedding,
            event_type=EventType.WELCOME_DRINK,
            name="Copo de Água",
            date=main_date,
            start_time=time(15, 0),
            end_time=time(17, 0),
            location=locations["hall"],
            requires_rsvp=True,
            requires_qr_code=True,
            display_order=40,
        )
        reception = WeddingEvent.objects.create(
            wedding=wedding,
            event_type=EventType.RECEPTION,
            name="Recepção",
            date=main_date,
            start_time=time(19, 30),
            end_time=time(23, 30),
            location=locations["hall"],
            dress_code="Traje de cerimónia",
            requires_rsvp=True,
            requires_qr_code=True,
            display_order=50,
        )
        xiguiane = WeddingEvent.objects.create(
            wedding=wedding,
            event_type=EventType.XIGUIANE,
            name="Xiguiane",
            description="Momento tradicional com a família e os vizinhos.",
            date=main_date + timedelta(days=1),
            start_time=time(10, 0),
            location=locations["family"],
            host_family="Família Cossa",
            requires_rsvp=True,
            show_to_all_guests=False,
            display_order=60,
        )
        return {
            "lobolo": lobolo,
            "religious": religious,
            "civil": civil,
            "welcome_drink": welcome_drink,
            "reception": reception,
            "xiguiane": xiguiane,
        }

    def _create_schedule(self, wedding: Wedding, events: dict, locations: dict) -> None:
        programme = [
            ("Cerimónia Religiosa", time(9, 0), events["religious"], locations["church"], "bi-bank"),
            ("Cerimónia Civil", time(11, 30), events["civil"], locations["church"], "bi-file-earmark-text"),
            ("Welcome Drink", time(14, 30), events["welcome_drink"], locations["hall"], "bi-cup-straw"),
            ("Copo de Água", time(15, 0), events["welcome_drink"], locations["hall"], "bi-cup-hot"),
            ("Sessão Fotográfica", time(15, 30), None, locations["hall"], "bi-camera"),
            ("Corte do Bolo", time(18, 30), events["reception"], locations["hall"], "bi-cake"),
            ("Abertura da Sala", time(19, 30), events["reception"], locations["hall"], "bi-door-open"),
        ]
        for position, (title, start, event, location, icon) in enumerate(programme, start=1):
            ScheduleItem.objects.create(
                wedding=wedding,
                title=title,
                start_time=start,
                date=event.date if event else wedding.main_date,
                event=event,
                location=location,
                icon=icon,
                display_order=position * 10,
            )
