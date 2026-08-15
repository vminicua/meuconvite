from django.apps import AppConfig


class WeddingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "weddings"
    verbose_name = "Eventos"

    def ready(self) -> None:
        # Pillow does not decode the HEIC/HEIF files produced by iPhones by
        # itself. Registering the plugin here also makes Django's ImageField
        # validation understand those files before they are normalised.
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except ImportError:
            # Deployment checks will flag a missing requirements install; the
            # application can still start so existing JPEG/PNG uploads work.
            pass
