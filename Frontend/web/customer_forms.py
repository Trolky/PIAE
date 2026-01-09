from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class FeedbackForm(forms.Form):
    """Feedback form used by customers.

    Notes:
        - Can be empty for APPROVE
        - Must be non-empty for REJECT (enforced in the view)
    """

    text: forms.CharField = forms.CharField(
        label=_("Feedback for translator"),
        widget=forms.Textarea(
            attrs={
                "class": "field__input",
                "rows": 5,
                "placeholder": _("Overall evaluation (optional for approve, required for reject)"),
            }
        ),
        required=False,
        max_length=2000,
    )
