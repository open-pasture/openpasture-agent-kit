"""Hermes plugin compatibility entry point for openPasture."""

from __future__ import annotations

from openpasture.connectors.hermes import register

__all__ = ["register"]
