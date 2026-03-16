"""Tests for react_agent.services.email_notifier."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock
from xml.etree.ElementTree import fromstring

import pytest

from react_agent.config import EmailConfig
from react_agent.services.email_notifier import EmailNotifier, EmailMessage


class TestEmailNotifier:
    def _make_config(self, **overrides) -> EmailConfig:
        defaults = dict(
            enabled=True,
            ddi_api_path="/usr/bin/ddi_api.pl",
            sender="agent@internal",
            recipients=["user@internal"],
            notify_on=["error", "heartbeat_failure"],
        )
        defaults.update(overrides)
        return EmailConfig(**defaults)

    def test_generate_mail_xml(self):
        notifier = EmailNotifier(self._make_config())
        xml_bytes = notifier._generate_xml(EmailMessage(subject="Test", body="Hello"))
        root = fromstring(xml_bytes)
        assert root.tag == "mail"
        assert root.find("from").text == "agent@internal"
        assert root.find("subject").text == "Test"
        assert root.find("body").text == "Hello"
        addresses = root.findall(".//address")
        assert len(addresses) == 1
        assert addresses[0].text == "user@internal"

    @patch("react_agent.services.email_notifier.subprocess.run")
    def test_send_calls_ddi_api(self, mock_run):
        notifier = EmailNotifier(self._make_config())
        notifier.send(EmailMessage(subject="S", body="B"))
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "/usr/bin/ddi_api.pl"
        assert call_args[1] == "MAIL"
        assert call_args[2] == "-f"

    def test_disabled_does_nothing(self):
        notifier = EmailNotifier(self._make_config(enabled=False))
        # Should not raise.
        notifier.notify("error", "Subject", "Body")

    @patch("react_agent.services.email_notifier.subprocess.run")
    def test_notify_on_filter(self, mock_run):
        notifier = EmailNotifier(self._make_config(notify_on=["error"]))
        notifier.notify("task_complete", "Done", "All done")
        mock_run.assert_not_called()
        notifier.notify("error", "Oops", "Something failed")
        mock_run.assert_called_once()

    @patch("react_agent.services.email_notifier.subprocess.run", side_effect=OSError("fail"))
    def test_ddi_api_failure_logged_not_crash(self, mock_run):
        notifier = EmailNotifier(self._make_config())
        # Should not raise.
        notifier.send(EmailMessage(subject="S", body="B"))

    @patch("react_agent.services.email_notifier.subprocess.run")
    def test_xml_cleanup_after_send(self, mock_run, tmp_path):
        notifier = EmailNotifier(self._make_config())
        notifier.send(EmailMessage(subject="S", body="B"))
        # The temp file should be cleaned up.
        xml_path = mock_run.call_args[0][0][3]
        assert not Path(xml_path).exists()
