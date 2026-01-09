from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

COMMON_TARGET_LANGUAGES: list[tuple[str, str | object]] = [
    ("cs", _("Czech (cs)")),
    ("sk", _("Slovak (sk)")),
    ("de", _("German (de)")),
    ("fr", _("French (fr)")),
    ("es", _("Spanish (es)")),
    ("it", _("Italian (it)")),
    ("pl", _("Polish (pl)")),
    ("pt", _("Portuguese (pt)")),
    ("nl", _("Dutch (nl)")),
    ("sv", _("Swedish (sv)")),
]


class LanguageAddForm(forms.Form):
    """Form for adding a translator language from a predefined set."""

    language_code: forms.ChoiceField = forms.ChoiceField(
        label=_("Translate to"),
        choices=COMMON_TARGET_LANGUAGES,
        widget=forms.Select(attrs={"class": "field__input"}),
    )

    def clean_language_code(self) -> str:
        return (self.cleaned_data["language_code"] or "").strip().lower()


class LanguageRemoveForm(forms.Form):
    """Form for removing a translator language (hidden input)."""

    language_code: forms.CharField = forms.CharField(min_length=2, max_length=2, widget=forms.HiddenInput())

    def clean_language_code(self) -> str:
        code: str = (self.cleaned_data["language_code"] or "").strip().lower()
        if len(code) != 2 or not code.isalpha():
            raise forms.ValidationError(_("Invalid language code"))
        return code
