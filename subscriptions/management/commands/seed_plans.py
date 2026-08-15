"""
Cria (ou actualiza) os pacotes comerciais.

    python manage.py seed_plans

É seguro correr várias vezes: identifica cada pacote pelo código e só
altera o que mudou. Por omissão **não** mexe nos preços de pacotes que já
existam — para isso use `--update-prices`, para que uma tabela de preços
ajustada na administração não seja apagada por um deploy.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from subscriptions.models import Plan

# O plano gratuito é deliberadamente limitado: 5 convidados e sem envios por SMS.
# Os preços são um ponto de partida e devem ser confirmados na administração.
PLANS: list[dict] = [
    {
        "code": "gratuito",
        "name": "Gratuito",
        "description": "Para experimentar a plataforma e eventos pequenos.",
        "max_guests": 5,
        "max_events": 1,
        "max_sms": 0,
        "price_mzn": Decimal("0"),
        "duration_days": 0,
        "templates_limit": 0,
        "allows_qr_checkin": True,
        "allows_seating": True,
        "allows_exports": True,
        "allows_team": True,
        "is_default": True,
        "display_order": 10,
    },
    {
        "code": "essencial-50",
        "name": "Essencial 50",
        "description": "Até 50 convidados, com convites individuais e QR Code.",
        "max_guests": 50,
        "max_events": 1,
        "max_sms": 50,
        "price_mzn": Decimal("1500"),
        "duration_days": 365,
        "allows_qr_checkin": True,
        "allows_exports": True,
        "templates_limit": 0,
        "allows_team": True,
        "display_order": 20,
    },
    {
        "code": "celebracao-100",
        "name": "Celebração 100",
        "description": "Até 100 convidados, com mesas e exportações.",
        "max_guests": 100,
        "max_events": 1,
        "max_sms": 150,
        "price_mzn": Decimal("2500"),
        "duration_days": 365,
        "allows_qr_checkin": True,
        "allows_seating": True,
        "allows_exports": True,
        "allows_team": True,
        "templates_limit": 0,
        "display_order": 30,
    },
    {
        "code": "premium-200",
        "name": "Premium 200",
        "description": "Até 200 convidados, equipa e relatórios completos.",
        "max_guests": 200,
        "max_events": 1,
        "max_sms": 400,
        "price_mzn": Decimal("4500"),
        "duration_days": 365,
        "allows_qr_checkin": True,
        "allows_seating": True,
        "allows_team": True,
        "allows_exports": True,
        "removes_branding": True,
        "templates_limit": 0,
        "display_order": 40,
    },
    {
        "code": "grande-evento-500",
        "name": "Grande Evento 500",
        "description": "Até 500 convidados, sem marca da plataforma.",
        "max_guests": 500,
        "max_events": 1,
        "max_sms": 1000,
        "price_mzn": Decimal("6000"),
        "duration_days": 365,
        "allows_qr_checkin": True,
        "allows_seating": True,
        "allows_team": True,
        "allows_exports": True,
        "removes_branding": True,
        "templates_limit": 0,
        "display_order": 50,
        "is_active": False,
    },
]

# Catálogo oficial por tipo de evento (Preços.xlsx, 12/08/2026).
_MATRIX = {
    "wedding": [
        ("free", "Free", 0, 10, 0, 1), ("classic", "Classic", 9500, 100, 100, 4),
        ("premium", "Premium", 14500, 150, 200, 8), ("prestige", "Prestige", 23500, 200, 300, 10),
        ("royal", "Royal", 36500, 300, 600, 15),
    ],
    "celebration": [
        ("free", "Free", 0, 5, 0, 1), ("graduate", "Graduate", 4500, 50, 50, 4),
        ("celebration", "Celebration", 8500, 100, 100, 8), ("class", "Class", 13500, 150, 200, 10),
        ("grand-class", "Grand Class", 21500, 200, 300, 15),
    ],
    "engagement": [
        ("free", "Free", 0, 5, 0, 1), ("elegant", "Elegant", 5000, 50, 50, 4),
        ("premium", "Premium", 8000, 100, 100, 8), ("exclusive", "Exclusive", 13000, 150, 200, 10),
    ],
    "corporate": [
        ("free", "Free", 0, 5, 0, 1), ("business", "Business", 11500, 50, 100, 5),
        ("professional", "Professional", 19500, 100, 200, 8),
        ("plus", "Corporate Plus", 41500, 250, 500, 10), ("enterprise", "Enterprise", 68500, 500, 1000, 15),
    ],
}
PLANS = [
    {
        "code": f"{family}-{slug}", "name": name,
        "description": f"Plano {name} para esta categoria de evento.",
        "event_family": family, "max_guests": guests, "max_events": 1,
        "max_sms": sms, "max_team": team, "price_mzn": Decimal(price),
        "duration_days": 0 if price == 0 else 365, "templates_limit": 0,
        "allows_qr_checkin": True, "allows_seating": True,
        "allows_exports": True, "allows_team": True, "is_default": price == 0,
        "display_order": order * 10,
    }
    for family, rows in _MATRIX.items()
    for order, (slug, name, price, guests, sms, team) in enumerate(rows, 1)
]


class Command(BaseCommand):
    help = "Cria ou actualiza os pacotes de subscrição."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--update-prices",
            action="store_true",
            help="Também actualiza os preços de pacotes já existentes.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        update_prices = options["update_prices"]
        created_count = 0
        updated_count = 0

        for definition in PLANS:
            data = dict(definition)
            code = data.pop("code")
            price = data.pop("price_mzn")

            plan, created = Plan.objects.get_or_create(
                code=code, defaults={**data, "price_mzn": price}
            )
            if created:
                created_count += 1
                self.stdout.write(f"  criado: {plan.name} ({plan.max_guests} convidados)")
                continue

            changed = []
            for field, value in data.items():
                if getattr(plan, field) != value:
                    setattr(plan, field, value)
                    changed.append(field)
            if update_prices and plan.price_mzn != price:
                plan.price_mzn = price
                changed.append("price_mzn")

            if changed:
                plan.full_clean()
                plan.save()
                updated_count += 1
                self.stdout.write(f"  actualizado: {plan.name} ({', '.join(changed)})")

        current_codes = {definition["code"] for definition in PLANS}
        Plan.objects.exclude(code__in=current_codes).update(is_active=False, is_default=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Pacotes prontos: {created_count} criado(s), {updated_count} actualizado(s), "
                f"{Plan.objects.count()} no total."
            )
        )
        if not update_prices:
            self.stdout.write(
                self.style.WARNING(
                    "Os preços dos pacotes já existentes não foram alterados. "
                    "Confirme a tabela de preços na administração "
                    "(ou use --update-prices)."
                )
            )
