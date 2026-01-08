from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _


class LoginForm(forms.Form):
    """Login form.

    Fields:
        method: Login method (password or OTP).
        username: Username.
        password: Plaintext password (required for password login).
        otp: One-time code (required for OTP login).
    """

    METHOD_CHOICES = (
        ("password", _("Password")),
        ("otp", _("One-time code (OTP)")),
    )

    method = forms.ChoiceField(
        label=_("Login method"),
        choices=METHOD_CHOICES,
        initial="password",
        widget=forms.Select(attrs={"class": "field__input"}),
        required=True,
        help_text=_("OTP requires prior activation after password login."),
    )

    username = forms.CharField(
        label=_("Username"),
        min_length=1,
        help_text=_("Alphanumeric username"),
        widget=forms.TextInput(attrs={"class": "field__input", "autocomplete": "username"}),
    )

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "current-password"}),
        min_length=1,
        required=False,
    )

    otp = forms.CharField(
        label=_("One-time code"),
        min_length=4,
        max_length=12,
        required=False,
        widget=forms.TextInput(attrs={"class": "field__input", "autocomplete": "one-time-code"}),
    )

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("method")
        if method == "otp":
            if not (cleaned.get("otp") or "").strip():
                self.add_error("otp", _("OTP code is required."))
        else:
            if not (cleaned.get("password") or "").strip():
                self.add_error("password", _("Password is required."))
        return cleaned


class RegisterForm(forms.Form):
    """Registration form.

    Fields:
        name: Alphanumeric username.
        email_address: Email.
        role: CUSTOMER or TRANSLATOR.
        password: Plaintext password.
        password_confirm: Password confirmation.
    """

    name = forms.CharField(
        label=_("Username"),
        min_length=1,
        widget=forms.TextInput(attrs={"class": "field__input", "autocomplete": "username"}),
    )
    email_address = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={"class": "field__input", "autocomplete": "email"}),
    )
    role = forms.ChoiceField(
        label=_("Role"),
        choices=(
            ("CUSTOMER", _("Customer")),
            ("TRANSLATOR", _("Translator")),
        ),
        widget=forms.Select(attrs={"class": "field__input"}),
    )

    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "new-password"}),
        min_length=8,
        help_text=_("Minimum 8 characters and at least one of them must be a number."),
    )
    password_confirm = forms.CharField(
        label=_("Confirm password"),
        widget=forms.PasswordInput(attrs={"class": "field__input", "autocomplete": "new-password"}),
        min_length=8,
    )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"]
        if not name.isalnum():
            raise forms.ValidationError(_("Username must be alphanumeric."))
        return name

    def clean_password(self) -> str:
        pwd = self.cleaned_data["password"]
        if not any(c.isalpha() for c in pwd) or not any(c.isdigit() for c in pwd):
            raise forms.ValidationError(_("Password must contain at least one letter and one number."))
        return pwd

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get("password")
        pwd2 = cleaned.get("password_confirm")
        if pwd and pwd2 and pwd != pwd2:
            self.add_error("password_confirm", _("Passwords do not match."))
        return cleaned
