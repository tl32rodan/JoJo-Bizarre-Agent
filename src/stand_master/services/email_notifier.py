"""Email notifier using internal ddi_api.pl MAIL utility."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from stand_master.config import EmailConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    subject: str
    body: str


class EmailNotifier:
    def __init__(self, config: EmailConfig) -> None:
        self._config = config

    def notify(self, event_type: str, subject: str, body: str) -> None:
        if not self._config.enabled or event_type not in self._config.notify_on:
            return
        self.send(EmailMessage(subject=subject, body=body))

    def send(self, message: EmailMessage) -> None:
        if not self._config.enabled:
            return
        xml_bytes = self._generate_xml(message)
        self._invoke_ddi_api(xml_bytes)

    def _generate_xml(self, message: EmailMessage) -> bytes:
        root = Element("mail")
        SubElement(root, "from").text = self._config.sender
        to_el = SubElement(root, "to")
        for addr in self._config.recipients:
            SubElement(to_el, "address").text = addr
        SubElement(root, "subject").text = message.subject
        SubElement(root, "body").text = message.body
        return tostring(root, encoding="unicode").encode("utf-8")

    def _invoke_ddi_api(self, xml_bytes: bytes) -> None:
        tmp_file = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="wb")
            tmp_file.write(xml_bytes)
            tmp_file.close()
            subprocess.run(
                [self._config.ddi_api_path, "MAIL", "-f", tmp_file.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=30, check=False,
            )
        except Exception:
            logger.exception("Failed to send email via ddi_api.pl")
        finally:
            if tmp_file is not None:
                try:
                    Path(tmp_file.name).unlink(missing_ok=True)
                except OSError:
                    pass
