#!/usr/bin/env python3
"""
Tests de la validación de CSV descargado en download_current_season (issue #79).

Agujero: cuando el CSV de la temporada aún no existe, football-data.co.uk NO
devuelve 404 consistente — a veces hace fuzzy-redirect (3xx) al fichero «más
parecido» de OTRA liga, a veces devuelve 300 con cuerpo HTML. El código antiguo
(`requests.get(url, timeout=30)` + `raise_for_status()`) seguía la redirección
y no fallaba con 3xx, así que ingería el CSV escocés como La Liga y el HTML
reventaba `process_season`.

Contrato verificado (issue #79):
  1. `allow_redirects=False` y cualquier status != 200 => results[lg] = None.
  2. Validación de contenido: primera columna `Div` (BOM-tolerante) y valor de
     `Div` en datos == código esperado de la liga (derivado de URLS).
  3. Con results[lg] = None el flujo cae en las ramas existentes (no probado
     aquí: es integración de update_data; aquí se prueba el punto de decisión).

DoD del issue: CSV con Div incorrecto => None; CSV con HTML => None; CSV válido
con BOM => aceptado. Sin red ni pandas: monkeypatch de update.requests.

Ejecutable standalone con exit code (asserts):
    python3 test_csv_validation.py
"""
import os
import tempfile

import update

CS_DIV = update.EXPECTED_DIV  # ll->SP1, pl->E0, ...

# --- CSVs sintéticos ---------------------------------------------------------
VALID_SP1 = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
    "SP1,15/08/2026,Barcelona,Real Madrid,2,1,H\n"
    "SP1,16/08/2026,Sevilla,Valencia,0,0,D\n"
)
# Mismo contenido pero con BOM UTF-8 al inicio (football-data lo sirve así a
# menudo). Dos formas que hay que tolerar:
#   - U+FEFF: cuando requests decodifica el cuerpo como utf-8.
#   - `ï»¿` (mojibake): los tres bytes del BOM UTF-8 leídos como latin-1, que
#     es lo que ocurre en el cron real y la forma que el issue #79 cita literal.
VALID_SP1_BOM = "﻿" + VALID_SP1
VALID_SP1_BOM_MOJIBAKE = "ï»¿" + VALID_SP1
# Fuzzy-redirect: CSV del Championship escocés (SC1) servido en la URL de SP1.
WRONG_LEAGUE_SC1 = (
    "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
    "SC1,08/08/2026,Arbroath,Ayr,1,3,A\n"
    "SC1,09/08/2026,Dunfermline,Falkirk,2,2,D\n"
)
# Status 300 con cuerpo HTML (lo que pasa hoy con I1/D1/F1).
HTML_300 = (
    "<!DOCTYPE html>\n<html><head><title>300 Multiple Choices</title></head>\n"
    "<body><h1>Multiple Choices</h1></body></html>\n"
)


def test_valid_csv_accepted():
    ok, reason = update.validate_csv_content(VALID_SP1, 'SP1')
    assert ok, f"CSV válido de SP1 debe aceptarse, got reason={reason!r}"
    print("OK CSV válido (Div=SP1) aceptado")


def test_valid_csv_with_bom_accepted():
    """DoD: CSV válido con BOM => aceptado. Ambas formas (U+FEFF y el mojibake
    `ï»¿` que el issue #79 cita literal y que produce el cron real)."""
    ok, reason = update.validate_csv_content(VALID_SP1_BOM, 'SP1')
    assert ok, f"CSV válido con BOM U+FEFF debe aceptarse, got reason={reason!r}"
    ok_m, reason_m = update.validate_csv_content(VALID_SP1_BOM_MOJIBAKE, 'SP1')
    assert ok_m, f"CSV válido con BOM mojibake ï»¿ debe aceptarse, got reason={reason_m!r}"
    print("OK CSV válido con BOM aceptado (U+FEFF y mojibake ï»¿)")


def test_wrong_league_rejected():
    """DoD: CSV con Div incorrecto (fuzzy-redirect a otra liga) => None."""
    ok, reason = update.validate_csv_content(WRONG_LEAGUE_SC1, 'SP1')
    assert not ok, "CSV de otra liga (SC1) NO debe aceptarse como SP1"
    assert 'SC1' in reason and 'SP1' in reason, \
        f"el motivo debe citar Div encontrado y esperado, got {reason!r}"
    print(f"OK CSV de otra liga rechazado ({reason})")


def test_html_rejected():
    """DoD: cuerpo HTML (status 300) => None."""
    ok, reason = update.validate_csv_content(HTML_300, 'I1')
    assert not ok, "un cuerpo HTML NO debe aceptarse como CSV"
    assert 'Div' in reason, f"el motivo debe señalar columna != Div, got {reason!r}"
    print(f"OK cuerpo HTML rechazado ({reason})")


def test_empty_and_headeronly_rejected():
    assert not update.validate_csv_content("", 'SP1')[0], "vacío => rechazado"
    assert not update.validate_csv_content("Div,Date,HomeTeam\n", 'SP1')[0], \
        "solo header sin filas de datos => rechazado"
    print("OK vacío y solo-header rechazados")


def test_expected_div_derived_from_urls():
    """El mapeo esperado se deriva de URLS, no se hardcodea aparte."""
    assert CS_DIV == {
        'll': 'SP1', 'pl': 'E0', 'sa': 'I1',
        'bl': 'D1', 'l1': 'F1', 'ed': 'N1',
    }, f"EXPECTED_DIV inesperado: {CS_DIV}"
    print("OK EXPECTED_DIV derivado de URLS")


class _FakeResp:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


class _FakeRequests:
    """Sustituye a update.requests: sirve por URL y registra kwargs."""
    def __init__(self, by_url):
        self.by_url = by_url
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        status, text = self.by_url[url]
        return _FakeResp(status, text)


def _run_download_with(by_url):
    orig_req = update.requests
    orig_dir = update.DATA_DIR
    fake = _FakeRequests(by_url)
    tmp = tempfile.mkdtemp()
    update.requests = fake
    update.DATA_DIR = tmp
    try:
        results = update.download_current_season()
    finally:
        update.requests = orig_req
        update.DATA_DIR = orig_dir
    return results, fake, tmp


def test_download_passes_allow_redirects_false():
    """Contrato 1: allow_redirects=False en cada requests.get."""
    by_url = {url: (200, VALID_SP1 if update.EXPECTED_DIV[lg] == 'SP1'
                    else f"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
                         f"{update.EXPECTED_DIV[lg]},15/08/2026,A,B,1,0,H\n")
              for lg, url in update.URLS.items()}
    results, fake, tmp = _run_download_with(by_url)
    assert all(kw.get('allow_redirects') is False for _, kw in fake.calls), \
        "cada requests.get debe pasar allow_redirects=False"
    # Todas las ligas válidas => path escrito y fichero en disco.
    for lg in update.URLS:
        assert results[lg] is not None, f"{lg} válido debe devolver path"
        assert os.path.exists(results[lg]), f"{lg}: el CSV debe escribirse"
    print("OK download: allow_redirects=False y CSVs válidos escritos")


def test_download_rejects_redirect_and_wrong_league_and_html():
    """Contrato 1+2: 3xx => None; otra liga => None; HTML(300) => None."""
    urls = update.URLS
    by_url = {
        urls['ll']: (301, ""),                 # redirect => None
        urls['pl']: (200, WRONG_LEAGUE_SC1),   # 200 pero otra liga => None
        urls['sa']: (300, HTML_300),           # HTML 300 => None
        urls['bl']: (200, "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
                          "D1,15/08/2026,Bayern,Dortmund,3,1,H\n"),  # válido
        urls['l1']: (200, "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
                          "F1,15/08/2026,PSG,Lyon,2,0,H\n"),          # válido
        urls['ed']: (404, ""),                 # 404 => None
    }
    results, fake, tmp = _run_download_with(by_url)
    assert results['ll'] is None, "301 redirect => None"
    assert results['pl'] is None, "CSV de otra liga (SC1) => None"
    assert results['sa'] is None, "HTML 300 => None"
    assert results['ed'] is None, "404 => None"
    assert results['bl'] is not None and os.path.exists(results['bl']), \
        "D1 válido => path escrito"
    assert results['l1'] is not None and os.path.exists(results['l1']), \
        "F1 válido => path escrito"
    print("OK download: redirect/otra-liga/HTML/404 => None; válidos escritos")


if __name__ == '__main__':
    test_valid_csv_accepted()
    test_valid_csv_with_bom_accepted()
    test_wrong_league_rejected()
    test_html_rejected()
    test_empty_and_headeronly_rejected()
    test_expected_div_derived_from_urls()
    test_download_passes_allow_redirects_false()
    test_download_rejects_redirect_and_wrong_league_and_html()
    print("\nTODOS LOS TESTS OK (validación CSV, issue #79)")
