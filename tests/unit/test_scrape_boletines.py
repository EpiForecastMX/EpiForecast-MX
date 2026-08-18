"""Contratos de descarga del scraper de boletines SINAVE.

Cubren la causa del fallo del 2026-08-18: gob.mx respondio 403 a la descarga directa
porque `requests` mandaba su User-Agent por defecto, mientras que la navegacion con
Selenium si pasaba el muro. El boletin de la semana 31 existia y estaba publicado; lo
que fallo fue bajarlo.

`selenium` vive en el extra `scraping`, que el flujo de pruebas no instala, asi que
este modulo se omite salvo que este presente. Corre en local y en cualquier entorno
que instale ese extra.
"""

import contextlib
from pathlib import Path

import pytest

pytest.importorskip("selenium", reason="scrape_boletines requiere el extra 'scraping'")

from scripts import scrape_boletines as sb  # noqa: E402

PDF_OK = b"%PDF-1.7\n" + b"x" * 4096


class _FakeResponse:
    """Respuesta minima con la superficie que usa download_pdf."""

    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise sb.requests.HTTPError(f"{self.status_code} Client Error")

    def iter_content(self, chunk: int):
        for i in range(0, len(self._body), chunk):
            yield self._body[i : i + chunk]


@pytest.fixture
def captura_get(monkeypatch):
    """Sustituye requests.get y guarda con que argumentos fue llamado."""
    llamadas: list[dict] = []
    caja: dict = {"respuesta": _FakeResponse(PDF_OK)}

    def _fake_get(url, **kwargs):
        llamadas.append({"url": url, "kwargs": kwargs})
        return caja["respuesta"]

    monkeypatch.setattr(sb.requests, "get", _fake_get)
    return llamadas, caja


def test_la_descarga_va_con_user_agent_de_navegador(tmp_path: Path, captura_get) -> None:
    """El 403 venia de aqui: sin este encabezado, gob.mx rechaza la descarga."""
    llamadas, _ = captura_get
    sb.download_pdf("https://example.test/sem31.pdf", tmp_path / "2026_sem31.pdf")

    headers = llamadas[0]["kwargs"]["headers"]
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "python-requests" not in headers["User-Agent"]


def test_selenium_y_la_descarga_declaran_el_mismo_agente() -> None:
    """Una sola fuente de verdad: si se cambia una, no puede quedarse la otra atras."""
    assert sb.DOWNLOAD_HEADERS["User-Agent"] == sb.BROWSER_USER_AGENT


def test_guarda_el_pdf_cuando_la_respuesta_es_valida(tmp_path: Path, captura_get) -> None:
    dest = tmp_path / "2026_sem31.pdf"
    sb.download_pdf("https://example.test/sem31.pdf", dest)

    assert dest.read_bytes() == PDF_OK


def test_una_respuesta_que_no_es_pdf_no_deja_archivo(tmp_path: Path, captura_get) -> None:
    """Falla cerrado: un portal que devuelve HTML de error no debe pasar por boletin."""
    _, caja = captura_get
    caja["respuesta"] = _FakeResponse(b"<html><body>Acceso denegado</body></html>" + b" " * 2048)
    dest = tmp_path / "2026_sem31.pdf"

    with pytest.raises(sb.NotAPdfError):
        sb.download_pdf("https://example.test/sem31.pdf", dest)

    assert not dest.exists()


def test_una_respuesta_truncada_no_deja_archivo(tmp_path: Path, captura_get) -> None:
    _, caja = captura_get
    caja["respuesta"] = _FakeResponse(b"%PDF-1.7\n")
    dest = tmp_path / "2026_sem31.pdf"

    with pytest.raises(sb.NotAPdfError):
        sb.download_pdf("https://example.test/sem31.pdf", dest)

    assert not dest.exists()


def test_un_error_http_no_deja_archivo(tmp_path: Path, captura_get) -> None:
    _, caja = captura_get
    caja["respuesta"] = _FakeResponse(b"", status=403)
    dest = tmp_path / "2026_sem31.pdf"

    with pytest.raises(sb.requests.HTTPError):
        sb.download_pdf("https://example.test/sem31.pdf", dest)

    assert not dest.exists()


@pytest.mark.parametrize(
    "cuerpo, status",
    [(PDF_OK, 200), (b"<html>no</html>" + b" " * 2048, 200), (b"", 403)],
)
def test_nunca_sobrevive_el_archivo_temporal(tmp_path: Path, captura_get, cuerpo, status) -> None:
    """Ni al triunfar ni al fallar: un .part olvidado confunde al inventario del pipeline."""
    _, caja = captura_get
    caja["respuesta"] = _FakeResponse(cuerpo, status=status)
    dest = tmp_path / "2026_sem31.pdf"

    with contextlib.suppress(Exception):
        sb.download_pdf("https://example.test/sem31.pdf", dest)

    assert list(tmp_path.glob("*.part")) == []


def test_un_pdf_previo_sobrevive_a_una_descarga_fallida(tmp_path: Path, captura_get) -> None:
    """La escritura es atomica: el boletin bueno de ayer no se pierde por el 403 de hoy."""
    _, caja = captura_get
    dest = tmp_path / "2026_sem31.pdf"
    dest.write_bytes(PDF_OK)
    caja["respuesta"] = _FakeResponse(b"<html>403</html>" + b" " * 2048)

    with pytest.raises(sb.NotAPdfError):
        sb.download_pdf("https://example.test/sem31.pdf", dest)

    assert dest.read_bytes() == PDF_OK
