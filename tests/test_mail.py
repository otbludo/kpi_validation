"""
Tests du service d'envoi de mail : rendu des templates HTML et envoi
via SMTP (smtplib mocké, aucun envoi réel).
"""
import pytest
import app.services.mailtrap.mail_service as mail_module
from app.services.mailtrap.mail_service import MailService


@pytest.fixture
def service():
    return MailService()


# ---------------------------------------------------------------------------
# _load_template
# ---------------------------------------------------------------------------

def test_load_template_replaces_variables(service):
    html = service._load_template(
        "warning",
        user_name="Alice",
        invalid_fields="<li>Sexe</li>",
        total_percentage=88.24,
    )

    assert "Alice" in html
    assert "{{user_name}}" not in html


def test_load_template_warning_injects_fields(service):
    html = service._load_template(
        "warning",
        user_name="Bob",
        invalid_fields="<li>Sexe</li>",
        total_percentage=88.24,
    )

    assert "Bob" in html
    assert "<li>Sexe</li>" in html
    assert "88.24" in html


def test_load_template_missing_raises(service):
    with pytest.raises(FileNotFoundError):
        service._load_template("inexistant")


# ---------------------------------------------------------------------------
# send_email (SMTP mocké)
# ---------------------------------------------------------------------------

class _FakeSMTP:
    instances = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = False
        self.sent_message = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = True

    def send_message(self, message):
        self.sent_message = message


def test_send_email_success(service, monkeypatch):
    _FakeSMTP.instances = []
    monkeypatch.setattr(mail_module.smtplib, "SMTP", _FakeSMTP)

    ok = service.send_email(
        email_to="dest@example.com",
        subject="Sujet",
        template_name="warning",
        user_name="Alice",
        invalid_fields="<li>Sexe</li>",
        total_percentage=88.24,
    )

    assert ok is True
    smtp = _FakeSMTP.instances[-1]
    assert smtp.started_tls is True
    assert smtp.logged_in is True
    assert smtp.sent_message["To"] == "dest@example.com"
    assert smtp.sent_message["Subject"] == "Sujet"


def test_send_email_raises_http_exception_on_failure(service, monkeypatch):
    from fastapi import HTTPException

    def boom(host, port):
        raise Exception("connexion refusée")

    monkeypatch.setattr(mail_module.smtplib, "SMTP", boom)

    with pytest.raises(HTTPException):
        service.send_email(
            email_to="dest@example.com",
            subject="Sujet",
            template_name="warning",
            user_name="Alice",
            invalid_fields="<li>Sexe</li>",
            total_percentage=88.24,
        )
