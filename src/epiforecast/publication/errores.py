"""Excepción del sello, en un módulo sin dependencias para que nadie importe en círculo."""

from __future__ import annotations


class StagingError(RuntimeError):
    """El staging no puede sellarse o aplicarse tal como está."""
