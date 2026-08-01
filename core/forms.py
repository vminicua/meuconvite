"""Form helpers shared by every application."""

from __future__ import annotations

from django import forms


class BootstrapFormMixin:
    """
    Applies Bootstrap 5 classes to every widget automatically.

    Explicit classes set on a widget are preserved, so a form can still
    opt out field by field.
    """

    error_css_class = "is-invalid"
    required_css_class = "required"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if widget.attrs.get("class"):
                self._apply_native_pickers(widget)
                continue

            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs["class"] = "form-check-input"
            elif isinstance(widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                # Os attrs pertencem ao contentor, não a cada input. A classe
                # `form-check-input` aqui encolhia a lista inteira para 1em.
                widget.attrs["class"] = "choice-list"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs["class"] = "form-select"
            elif isinstance(widget, (forms.FileInput, forms.ClearableFileInput)):
                widget.attrs["class"] = "form-control"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "form-control"
                widget.attrs.setdefault("rows", 4)
            elif isinstance(widget, (forms.HiddenInput,)):
                continue
            else:
                widget.attrs["class"] = "form-control"

            self._apply_native_pickers(widget)

    @staticmethod
    def _apply_native_pickers(widget) -> None:
        """
        Native HTML date/time pickers need ISO values, regardless of the
        Portuguese display format used elsewhere in the interface.
        """
        if isinstance(widget, forms.DateInput):
            widget.input_type = "date"
            widget.format = "%Y-%m-%d"
        elif isinstance(widget, forms.TimeInput):
            widget.input_type = "time"
            widget.format = "%H:%M"


class BootstrapForm(BootstrapFormMixin, forms.Form):
    pass


class BootstrapModelForm(BootstrapFormMixin, forms.ModelForm):
    pass
