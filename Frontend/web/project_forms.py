from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from web.language_forms import COMMON_TARGET_LANGUAGES


class ProjectCreateForm(forms.Form):
    """Form for creating a new translation project.

    Fields:
        language_code: Target language (ISO 639-1).
        original_file: Original source file (English).
    """

    language_code = forms.ChoiceField(
        label=_("Target language"),
        choices=COMMON_TARGET_LANGUAGES,
        widget=forms.Select(attrs={"class": "field__input"}),
    )

    original_file = forms.FileField(label=_("Source file (English)"))

    def clean_language_code(self) -> str:
        return (self.cleaned_data["language_code"] or "").strip().lower()

    def clean_original_file(self):
        f = self.cleaned_data["original_file"]
        if f is None:
            raise forms.ValidationError(_("File is required"))
        return f
