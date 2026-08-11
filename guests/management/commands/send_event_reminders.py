from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from guests.models import DeliveryStatus, EventReminderDelivery, Guest
from guests.reminders import send_event_reminder
from weddings.models import WeddingStatus


class Command(BaseCommand):
    help = "Envia lembretes por email aos convidados 7 e 1 dias antes do evento."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", nargs="+", type=int, default=[7, 1],
            help="Antecedências a processar (por omissão: 7 1).",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        today = timezone.localdate()
        sent = skipped = failed = 0
        for days_before in sorted(set(options["days"]), reverse=True):
            if days_before < 0:
                self.stderr.write(f"Ignorado valor negativo: {days_before}")
                continue
            event_date = today + timedelta(days=days_before)
            guests = Guest.objects.filter(
                is_active=True,
                email__gt="",
                wedding__status=WeddingStatus.PUBLISHED,
                wedding__main_date=event_date,
            ).select_related("wedding")
            for guest in guests.iterator():
                if options["dry_run"]:
                    self.stdout.write(f"[simulação] {guest.email} — {days_before} dia(s)")
                    continue
                try:
                    was_sent = EventReminderDelivery.objects.filter(
                        guest=guest,
                        event_date=guest.wedding.main_date,
                        days_before=days_before,
                        status=DeliveryStatus.SENT,
                    ).exists()
                    delivery = send_event_reminder(guest=guest, days_before=days_before)
                except Exception as exc:
                    failed += 1
                    self.stderr.write(f"Falhou {guest.email}: {exc}")
                    continue
                if was_sent:
                    skipped += 1
                else:
                    sent += 1
        self.stdout.write(self.style.SUCCESS(f"Lembretes: {sent} enviados, {skipped} já enviados, {failed} falharam."))
