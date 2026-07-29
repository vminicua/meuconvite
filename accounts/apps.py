from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Contas"

    def ready(self) -> None:  # noqa: D102
        from . import signals  # noqa: F401  (email verification sync only)
