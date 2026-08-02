from django.db import migrations


def apply_plan_rules(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Subscription = apps.get_model("subscriptions", "Subscription")

    Plan.objects.update(max_events=1, allows_qr_checkin=True)

    owner_ids = (
        Subscription.objects.filter(plan__price_mzn=0, status="active")
        .values_list("wedding__owner_id", flat=True)
        .distinct()
    )
    for owner_id in owner_ids.iterator():
        free_ids = list(
            Subscription.objects.filter(
                wedding__owner_id=owner_id,
                plan__price_mzn=0,
                status="active",
            )
            .order_by("wedding__created_at", "created_at")
            .values_list("pk", flat=True)
        )
        if len(free_ids) > 1:
            Subscription.objects.filter(pk__in=free_ids[1:]).update(status="pending")


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0006_payment_provider_payment_provider_checked_at_and_more")]
    operations = [migrations.RunPython(apply_plan_rules, migrations.RunPython.noop)]
