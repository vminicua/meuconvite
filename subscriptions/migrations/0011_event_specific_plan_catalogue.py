from decimal import Decimal

from django.db import migrations, models


CATALOGUE = {
    "wedding": [
        ("wedding-free", "Free", 0, 10, 0, 1),
        ("wedding-classic", "Classic", 9500, 100, 100, 4),
        ("wedding-premium", "Premium", 14500, 150, 200, 8),
        ("wedding-prestige", "Prestige", 23500, 200, 300, 10),
        ("wedding-royal", "Royal", 36500, 300, 600, 15),
    ],
    "celebration": [
        ("celebration-free", "Free", 0, 5, 0, 1),
        ("celebration-graduate", "Graduate", 4500, 50, 50, 4),
        ("celebration-celebration", "Celebration", 8500, 100, 100, 8),
        ("celebration-class", "Class", 13500, 150, 200, 10),
        ("celebration-grand-class", "Grand Class", 21500, 200, 300, 15),
    ],
    "engagement": [
        ("engagement-free", "Free", 0, 5, 0, 1),
        ("engagement-elegant", "Elegant", 5000, 50, 50, 4),
        ("engagement-premium", "Premium", 8000, 100, 100, 8),
        ("engagement-exclusive", "Exclusive", 13000, 150, 200, 10),
    ],
    "corporate": [
        ("corporate-free", "Free", 0, 5, 0, 1),
        ("corporate-business", "Business", 11500, 50, 100, 5),
        ("corporate-professional", "Professional", 19500, 100, 200, 8),
        ("corporate-plus", "Corporate Plus", 41500, 250, 500, 10),
        ("corporate-enterprise", "Enterprise", 68500, 500, 1000, 15),
    ],
}


def family_for(code):
    if code in {"casamento", "lobolo"}:
        return "wedding"
    if code == "noivado":
        return "engagement"
    if code == "evento-corporativo":
        return "corporate"
    return "celebration"


def create_catalogue(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Subscription = apps.get_model("subscriptions", "Subscription")
    new_codes = []
    free_by_family = {}
    for family, entries in CATALOGUE.items():
        for order, (code, name, price, guests, sms, team) in enumerate(entries, 1):
            plan, _ = Plan.objects.update_or_create(code=code, defaults={
                "name": name,
                "description": f"Plano {name} para esta categoria de evento.",
                "event_family": family,
                "max_guests": guests,
                "max_events": 1,
                "max_sms": sms,
                "max_team": team,
                "price_mzn": Decimal(price),
                "duration_days": 0 if price == 0 else 365,
                "allows_qr_checkin": True,
                "allows_seating": price > 0,
                "allows_team": True,
                "allows_exports": True,
                "removes_branding": False,
                "templates_limit": 0,
                "is_active": True,
                "is_default": price == 0,
                "display_order": order * 10,
            })
            new_codes.append(code)
            if price == 0:
                free_by_family[family] = plan

    Plan.objects.exclude(code__in=new_codes).update(is_active=False, is_default=False)

    # Eventos gratuitos existentes passam para o Free da sua categoria.
    for subscription in Subscription.objects.select_related("plan", "wedding__category"):
        if subscription.plan.price_mzn > 0:
            continue
        family = family_for(getattr(subscription.wedding.category, "code", ""))
        plan = free_by_family[family]
        subscription.plan = plan
        subscription.guest_allowance = plan.max_guests
        subscription.sms_allowance = 0
        subscription.save(update_fields=["plan", "guest_allowance", "sms_allowance", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0010_enable_exports_for_all_plans")]

    operations = [
        migrations.AddField(
            model_name="plan", name="event_family",
            field=models.CharField(
                choices=[
                    ("wedding", "Casamento / Lobolo"),
                    ("celebration", "Aniversário / Graduação / Batismo"),
                    ("engagement", "Noivado"),
                    ("corporate", "Eventos corporativos"),
                ],
                db_index=True, default="celebration", max_length=20,
                verbose_name="família de eventos",
            ),
        ),
        migrations.AddField(
            model_name="plan", name="max_team",
            field=models.PositiveIntegerField(default=1, verbose_name="membros da equipa"),
        ),
        migrations.RunPython(create_catalogue, migrations.RunPython.noop),
    ]
