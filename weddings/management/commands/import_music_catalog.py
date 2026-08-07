from __future__ import annotations

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from weddings.models import MusicTrack


TRACKS = (
    ("ordinary.mp3", "Ordinary — Wedding Dance", "Alex Warren", 10, True),
    ("bander-player-tambem-ama.mp3", "Player Também Ama", "Bander", 20, False),
    ("c4-pedro-casamento.mp3", "Casamento", "C4 Pedro", 30, False),
    ("puto-portugues-casamento.mp3", "Casamento", "Puto Português", 40, False),
    ("die-with-a-smile.mp3", "Die With A Smile", "Lady Gaga & Bruno Mars", 50, False),
)


class Command(BaseCommand):
    help = "Importa o catálogo inicial de músicas a partir de uma pasta local do servidor."

    def add_arguments(self, parser) -> None:
        parser.add_argument("directory", type=Path)
        parser.add_argument("--replace", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        directory: Path = options["directory"]
        missing = [filename for filename, *_rest in TRACKS if not (directory / filename).is_file()]
        if missing:
            raise CommandError(f"Ficheiros em falta: {', '.join(missing)}")

        for filename, title, artist, order, is_default in TRACKS:
            track, created = MusicTrack.objects.get_or_create(
                title=title,
                artist=artist,
                defaults={
                    "display_order": order,
                    "is_active": True,
                    "is_default": is_default,
                },
            )
            track.display_order = order
            track.is_active = True
            track.is_default = is_default
            if created or options["replace"] or not track.file:
                with (directory / filename).open("rb") as source:
                    track.file.save(filename, File(source), save=False)
            track.save()
            self.stdout.write(self.style.SUCCESS(f"{'Criada' if created else 'Atualizada'}: {track}"))
