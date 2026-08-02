"""Adiciona uma selecção editorial do Unsplash a um evento de demonstração."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max

from weddings.models import Wedding, WeddingGalleryPhoto


DEMO_PHOTOS = (
    ("_5_85Zqqsm4", "Allison Heine", "O lugar onde tudo fica mais leve: ao teu lado."),
    ("j4kR7-tWE2M", "Kadarius Seegars", "Rir contigo continua a ser o nosso plano favorito."),
    ("wHaQ4XJ9SgY", "Marc A. Sporys", "Entre sonhos, promessas e a certeza de termos encontrado casa."),
    ("nIKCy5CWIzk", "Jessica Felicio", "Um amor tranquilo, daqueles que crescem todos os dias."),
    ("JRc-08Hoe6c", "Tobe Mokolo", "A nossa aventura começou com um olhar e nunca mais parou."),
    ("3fl4xRSOD6k", "Eric Froehling", "Há abraços que dizem tudo sem precisar de palavras."),
    ("_3Sud4WPPYE", "Clay Banks", "Dois caminhos, uma história e tantos capítulos por viver."),
    ("3jTLp4o7jDc", "Samuel Rodriguez", "Escolher-te é a parte mais bonita de cada novo dia."),
    ("eDvztabelj8", "Kev Kombs", "As pequenas alegrias fizeram nascer a nossa grande história."),
    ("9B4hD5joEk4", "One zone Studio", "Para sempre começa aqui, rodeado de amor e de quem amamos."),
)


class Command(BaseCommand):
    help = "Adiciona 10 fotografias editoriais Unsplash a um evento específico."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wedding",
            required=True,
            help="UUID ou slug do evento que receberá a galeria de demonstração.",
        )

    def handle(self, *args, **options):
        identifier = options["wedding"]
        wedding = Wedding.objects.filter(slug=identifier).first()
        if wedding is None:
            try:
                wedding = Wedding.objects.filter(pk=identifier).first()
            except (TypeError, ValueError):
                wedding = None
        if wedding is None:
            raise CommandError(f"Evento não encontrado: {identifier}")

        next_order = wedding.gallery_photos.aggregate(value=Max("display_order"))["value"] or 0
        created = 0
        for offset, (photo_id, author, caption) in enumerate(DEMO_PHOTOS, start=1):
            image_url = f"https://unsplash.com/photos/{photo_id}/download?force=true&w=1800"
            credit_url = (
                f"https://unsplash.com/photos/{photo_id}"
                "?utm_source=meuconvite&utm_medium=referral"
            )
            _, was_created = WeddingGalleryPhoto.objects.get_or_create(
                wedding=wedding,
                external_url=image_url,
                defaults={
                    "caption": caption,
                    "credit_name": author,
                    "credit_url": credit_url,
                    "display_order": next_order + offset,
                    "is_visible": True,
                },
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Galeria de {wedding.display_names}: {created} fotografias adicionadas."
            )
        )
