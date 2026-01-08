from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class AdminMessageForm(forms.Form):
    """Form for administrator messages sent to customer/translator."""

    TO_CHOICES = (
        ("customer", _("Customer")),
        ("translator", _("Translator")),
    )

    to = forms.ChoiceField(label=_("To"), choices=TO_CHOICES, widget=forms.Select(attrs={"class": "field__input"}))
    subject = forms.CharField(
        label=_("Subject"),
        max_length=200,
        widget=forms.TextInput(attrs={"class": "field__input", "placeholder": _("Subject")}),
    )
    text = forms.CharField(
        label=_("Message"),
        max_length=4000,
        widget=forms.Textarea(attrs={"class": "field__input", "rows": 5, "placeholder": _("Message")}),
    )
