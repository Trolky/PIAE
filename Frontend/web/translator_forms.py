from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class TranslationUploadForm(forms.Form):
    """Form used by translators to upload the translated file."""

    translated_file: forms.FileField = forms.FileField(label=_("Translated file"))

    def clean_translated_file(self) -> forms.Field:
        f:  forms.Field = self.cleaned_data["translated_file"]
        if f is None:
            raise forms.ValidationError(_("File is required"))
        return f
