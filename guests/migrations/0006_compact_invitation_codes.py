import hashlib

from django.db import migrations, models

import core.utils


ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _fallback_code(seed: str, attempt: int) -> str:
    digest = hashlib.sha256(f"{seed}:{attempt}".encode()).digest()
    number = int.from_bytes(digest[:8], "big")
    chars = []
    for _ in range(4):
        number, index = divmod(number, len(ALPHABET))
        chars.append(ALPHABET[index])
    return "".join(chars)


def shorten_invitation_codes(apps, schema_editor):
    Guest = apps.get_model("guests", "Guest")
    rows = list(Guest.objects.order_by("created_at", "pk").values_list("pk", "invitation_token"))

    # Move every value out of the final namespace first, avoiding transient
    # unique-constraint collisions while existing codes are replaced.
    for guest_id, old_token in rows:
        temporary = "TMP" + hashlib.sha256(
            f"{guest_id}:{old_token}".encode()
        ).hexdigest()[:40]
        Guest.objects.filter(pk=guest_id).update(invitation_token=temporary)

    used = set()
    for guest_id, old_token in rows:
        candidate = (old_token or "")[:4]
        attempt = 0
        while len(candidate) != 4 or candidate.casefold() in used:
            candidate = _fallback_code(f"{guest_id}:{old_token}", attempt)
            attempt += 1
        used.add(candidate.casefold())
        Guest.objects.filter(pk=guest_id).update(invitation_token=candidate)


class Migration(migrations.Migration):
    dependencies = [("guests", "0005_invitationdelivery_counts_toward_limit")]

    operations = [
        migrations.RunPython(shorten_invitation_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="guest",
            name="invitation_token",
            field=models.CharField(
                default=core.utils.generate_invitation_code,
                editable=False,
                max_length=4,
                unique=True,
                verbose_name="codigo do convite",
            ),
        ),
    ]
