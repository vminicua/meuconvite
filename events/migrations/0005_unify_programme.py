from django.db import migrations


def unify_programme(apps, schema_editor):
    EventCategory = apps.get_model("events", "EventCategory")
    ScheduleItem = apps.get_model("events", "ScheduleItem")
    WeddingEvent = apps.get_model("events", "WeddingEvent")

    for category in EventCategory.objects.all().iterator():
        merged = list(category.default_moments or [])
        names = {str(item.get("name", "")).casefold() for item in merged if isinstance(item, dict)}
        for item in category.default_schedule or []:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            name = str(item["title"])
            if name.casefold() in names:
                continue
            merged.append({
                "name": name,
                "event_type": "custom",
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
                "requires_rsvp": False,
            })
            names.add(name.casefold())
        category.default_moments = merged
        category.default_schedule = []
        category.save(update_fields=["default_moments", "default_schedule"])

    for item in ScheduleItem.objects.select_related("wedding", "location").all().iterator():
        if WeddingEvent.objects.filter(wedding_id=item.wedding_id, name__iexact=item.title).exists():
            continue
        WeddingEvent.objects.create(
            wedding_id=item.wedding_id,
            name=item.title,
            event_type="custom",
            description=item.description,
            date=item.date,
            start_time=item.start_time,
            end_time=item.end_time,
            location_id=item.location_id,
            requires_rsvp=False,
            is_active=True,
            display_order=item.display_order,
        )


class Migration(migrations.Migration):
    dependencies = [("events", "0004_alter_scheduleitem_wedding_and_more")]
    operations = [migrations.RunPython(unify_programme, migrations.RunPython.noop)]
