from django.db import migrations


def disable_free_sms(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Subscription = apps.get_model("subscriptions", "Subscription")

    free_plan_ids = list(
        Plan.objects.filter(price_mzn=0).values_list("pk", flat=True)
    )
    Plan.objects.filter(pk__in=free_plan_ids).update(max_sms=0)
    Subscription.objects.filter(plan_id__in=free_plan_ids).update(sms_allowance=0)


def restore_previous_free_sms(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Subscription = apps.get_model("subscriptions", "Subscription")

    free_plan_ids = list(
        Plan.objects.filter(price_mzn=0).values_list("pk", flat=True)
    )
    Plan.objects.filter(pk__in=free_plan_ids).update(max_sms=10)
    Subscription.objects.filter(plan_id__in=free_plan_ids).update(sms_allowance=10)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0003_free_sms_limit_10")]

    operations = [
        migrations.RunPython(disable_free_sms, restore_previous_free_sms),
    ]
