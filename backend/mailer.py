"""
mailer.py — Sending emails behind one small interface.

Development uses ConsoleMailer: the email (with its link) is printed to the
server log and kept in `sent` so tests can read it. A production SMTP or
transactional-email mailer only has to implement `send`, then MAILER=<name>
selects it — no route code changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from backend.config import Settings

log = logging.getLogger("viralhook.mailer")


@dataclass
class Email:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, email: Email) -> None: ...


@dataclass
class ConsoleMailer:
    sent: list[Email] = field(default_factory=list)

    def send(self, email: Email) -> None:
        self.sent.append(email)
        print(f"\n[mailer] To: {email.to}\n[mailer] Subject: {email.subject}\n{email.body}\n", flush=True)
        log.info("email to %s: %s", email.to, email.subject)


_console = ConsoleMailer()


def get_mailer(settings: Settings) -> Mailer:
    if settings.mailer == "console":
        return _console
    raise RuntimeError(f"MAILER={settings.mailer!r} is not implemented yet (use 'console')")


def verify_email_message(to: str, name: str, link: str, hours: int) -> Email:
    return Email(to, "Verify your ViralHook email",
                 f"Hi {name},\n\nConfirm your email address for ViralHook:\n{link}\n\n"
                 f"The link is valid for {hours} hours. If you didn't sign up, ignore this email.")


def reset_password_message(to: str, name: str, link: str, minutes: int) -> Email:
    return Email(to, "Reset your ViralHook password",
                 f"Hi {name},\n\nSomeone asked to reset your ViralHook password. If it was you, open:\n"
                 f"{link}\n\nThe link is valid for {minutes} minutes and works once. "
                 "If it wasn't you, ignore this email; your password stays the same.")
