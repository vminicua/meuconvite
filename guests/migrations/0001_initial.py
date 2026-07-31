import uuid

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [("weddings", "0005_optional_address_and_event_attributes")]

    operations = [
        migrations.CreateModel(
            name="Guest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado em")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="activo")),
                ("full_name", models.CharField(max_length=160, verbose_name="nome completo")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="telefone")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email")),
                ("party_size", models.PositiveSmallIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(20)], verbose_name="lugares")),
                ("notes", models.CharField(blank=True, max_length=500, verbose_name="observações")),
                ("wedding", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="guests", to="weddings.wedding")),
            ],
            options={"verbose_name": "convidado", "verbose_name_plural": "convidados", "ordering": ["full_name"]},
        ),
        migrations.AddIndex(
            model_name="guest",
            index=models.Index(fields=["wedding", "is_active", "full_name"], name="guests_gues_wedding_e386a8_idx"),
        ),
    ]
