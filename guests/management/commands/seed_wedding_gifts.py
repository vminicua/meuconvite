from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from guests.models import Gift
from weddings.models import Wedding


WEDDING_GIFTS = [
    ("Jogo de panelas", "Conjunto de panelas para o dia a dia."),
    ("Serviço de jantar", "Pratos para receber família e amigos."),
    ("Talheres", "Conjunto completo de talheres."),
    ("Copos de água", "Conjunto de copos para a casa."),
    ("Taças de vinho", "Taças para momentos especiais."),
    ("Jogo de chá", "Bule, chávenas e pires."),
    ("Máquina de café", "Para começar as manhãs a dois."),
    ("Liquidificador", "Para sumos, molhos e receitas."),
    ("Batedeira", "Para bolos e sobremesas."),
    ("Micro-ondas", "Praticidade para a nova casa."),
    ("Torradeira", "Para pequenos-almoços especiais."),
    ("Air fryer", "Para refeições rápidas e saborosas."),
    ("Panela de pressão", "Uma ajuda essencial na cozinha."),
    ("Conjunto de facas", "Facas de cozinha de boa qualidade."),
    ("Tábua de cozinha", "Tábua resistente para preparação."),
    ("Jogo de recipientes", "Recipientes para organizar alimentos."),
    ("Toalha de mesa", "Uma toalha elegante para ocasiões especiais."),
    ("Jogo de lençóis", "Lençóis confortáveis para o casal."),
    ("Edredão", "Um edredão acolhedor para o quarto."),
    ("Conjunto de toalhas", "Toalhas de banho para o casal."),
    ("Almofadas", "Duas almofadas confortáveis."),
    ("Candeeiro de mesa", "Iluminação acolhedora para a casa."),
    ("Ferro de engomar", "Para cuidar da roupa do casal."),
    ("Tábua de engomar", "Complemento para a organização da roupa."),
    ("Aspirador", "Para manter a nova casa impecável."),
    ("Cesto de roupa", "Cesto para organizar a lavandaria."),
    ("Conjunto de decoração", "Peças decorativas para a nova casa."),
    ("Mala de viagem", "Para a primeira viagem do casal."),
    ("Álbum de fotografias", "Para guardar memórias da celebração."),
    ("Voucher para jantar", "Uma experiência especial para os noivos."),
]


class Command(BaseCommand):
    help = "Adiciona uma lista inicial de 30 presentes de casamento a um evento."

    def add_arguments(self, parser):
        parser.add_argument("wedding", help="UUID ou endereço público do evento.")

    @transaction.atomic
    def handle(self, *args, **options):
        identifier = options["wedding"]
        wedding = Wedding.objects.filter(pk=identifier).first() if len(identifier) == 36 else None
        wedding = wedding or Wedding.objects.filter(slug=identifier).first()
        if wedding is None:
            raise CommandError("Evento não encontrado.")

        created = 0
        for position, (name, description) in enumerate(WEDDING_GIFTS, start=1):
            gift, was_created = Gift.objects.get_or_create(
                wedding=wedding,
                name=name,
                defaults={
                    "description": description,
                    "display_order": position * 10,
                    "allow_multiple": False,
                },
            )
            if not was_created and not gift.is_active:
                gift.is_active = True
                gift.save(update_fields=["is_active", "updated_at"])
            created += int(was_created)

        total = Gift.objects.filter(wedding=wedding, is_active=True).count()
        self.stdout.write(self.style.SUCCESS(f"{created} presente(s) criado(s); {total} activo(s)."))
