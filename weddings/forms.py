from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.forms import BootstrapForm, BootstrapModelForm
from core.utils import unique_slugify

from .models import Wedding, WeddingMember, WeddingRole

User = get_user_model()


class WeddingCreateForm(BootstrapModelForm):
    """Step 1 of the wizard: who is getting married, when and where."""

    class Meta:
        model = Wedding
        fields = [
            "bride_full_name",
            "groom_full_name",
            "bride_short_name",
            "groom_short_name",
            "main_date",
            "city",
            "country",
        ]
        widgets = {
            "main_date": forms.DateInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "bride_short_name": _("Como aparecerá no convite. Por exemplo: Natércia."),
            "groom_short_name": _("Como aparecerá no convite. Por exemplo: Hivaldo."),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Derived from the full names in `clean()` when left empty.
        self.fields["bride_short_name"].required = False
        self.fields["groom_short_name"].required = False

    def clean_main_date(self):
        main_date = self.cleaned_data["main_date"]
        if main_date < timezone.localdate():
            raise forms.ValidationError(
                _("A data do casamento não pode estar no passado.")
            )
        return main_date

    def clean(self):
        cleaned = super().clean()
        # Short names are optional for the couple to think about: derive
        # them from the full names when left empty.
        if not cleaned.get("bride_short_name") and cleaned.get("bride_full_name"):
            cleaned["bride_short_name"] = cleaned["bride_full_name"].split()[0]
        if not cleaned.get("groom_short_name") and cleaned.get("groom_full_name"):
            cleaned["groom_short_name"] = cleaned["groom_full_name"].split()[0]
        return cleaned


class WeddingSettingsForm(BootstrapModelForm):
    """General settings of an existing wedding."""

    class Meta:
        model = Wedding
        fields = [
            "bride_full_name",
            "groom_full_name",
            "bride_short_name",
            "groom_short_name",
            "main_date",
            "city",
            "country",
            "slug",
            "hashtag",
            "welcome_message",
            "story",
            "rsvp_deadline",
            "show_countdown",
            "show_seat_before_event",
        ]
        widgets = {
            "main_date": forms.DateInput(),
            "rsvp_deadline": forms.DateInput(),
            "welcome_message": forms.Textarea(attrs={"rows": 3}),
            "story": forms.Textarea(attrs={"rows": 6}),
        }
        help_texts = {
            "slug": _("Endereço público: meuconvite.co.mz/<endereço>/"),
            "rsvp_deadline": _("Depois desta data deixam de ser aceites confirmações."),
        }

    def clean_slug(self) -> str:
        slug = (self.cleaned_data.get("slug") or "").strip().lower()
        if not slug:
            return unique_slugify(
                self.instance,
                f"{self.instance.bride_short_name}-e-{self.instance.groom_short_name}",
            )
        return slug

    def clean(self):
        cleaned = super().clean()
        deadline = cleaned.get("rsvp_deadline")
        main_date = cleaned.get("main_date")
        if deadline and main_date and deadline > main_date:
            self.add_error(
                "rsvp_deadline",
                _("O prazo de confirmação tem de ser anterior à data do casamento."),
            )
        return cleaned


class WeddingDesignForm(BootstrapModelForm):
    """Colours, cover photo and music."""

    class Meta:
        model = Wedding
        fields = [
            "selected_template",
            "primary_color",
            "secondary_color",
            "cover_image",
            "invitation_music",
            "show_music",
        ]
        widgets = {
            "primary_color": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "secondary_color": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
            "cover_image": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
            "invitation_music": forms.ClearableFileInput(attrs={"accept": "audio/mpeg,audio/mp4,audio/ogg"}),
        }


class MemberInviteForm(BootstrapForm):
    """Adds someone to the wedding team by email address."""

    email = forms.EmailField(
        label=_("Email do membro"),
        help_text=_("A pessoa tem de ter (ou criar) uma conta MeuConvite com este email."),
    )
    role = forms.ChoiceField(
        label=_("Função"),
        choices=[(value, label) for value, label in WeddingRole.choices if value != WeddingRole.OWNER],
        initial=WeddingRole.COMMITTEE,
    )
    notes = forms.CharField(label=_("Notas"), max_length=200, required=False)

    def __init__(self, *args, wedding: Wedding | None = None, **kwargs) -> None:
        self.wedding = wedding
        super().__init__(*args, **kwargs)

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower().strip()
        try:
            self.user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise forms.ValidationError(
                _(
                    "Não existe nenhuma conta com este email. Peça à pessoa para se "
                    "registar em %(site)s e tente novamente."
                )
                % {"site": "meuconvite.co.mz"}
            ) from None

        if self.wedding and self.user.pk == self.wedding.owner_id:
            raise forms.ValidationError(_("O proprietário já faz parte da equipa."))
        return email


class MemberPermissionsForm(BootstrapModelForm):
    """Fine-grained permissions for an existing member."""

    class Meta:
        model = WeddingMember
        fields = [
            "role",
            "can_manage_guests",
            "can_manage_events",
            "can_manage_seating",
            "can_check_in",
            "can_view_reports",
            "can_manage_design",
            "can_manage_billing",
            "notes",
        ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            (value, label) for value, label in WeddingRole.choices if value != WeddingRole.OWNER
        ]
