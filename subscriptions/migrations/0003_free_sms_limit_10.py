from django.db import migrations


def set_free_sms_limit(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    Subscription = apps.get_model("subscriptions", "Subscription")
    plan = Plan.objects.filter(code="gratuito").first()
    if plan is None:
        return
    plan.max_sms = 10
    plan.save(update_fields=["max_sms", "updated_at"])
    Subscription.objects.filter(plan=plan, status="active").update(sms_allowance=10)


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0002_plan_max_sms_subscription_sms_allowance")]
    operations = [migrations.RunPython(set_free_sms_limit, migrations.RunPython.noop)]
