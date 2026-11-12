"""Extrae productos para los códigos postales del centro de Madrid.

Reutiliza filas de Cabo de Palos cuando coinciden categoría, subcategoría,
nombre, formato y precio. Los nuevos productos se guardan sin preprocesar.

Desde Proyecto-1:
    uv run python src/proyecto_1/browser_madrid_centro.py
"""
from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "Data"
CP_INPUT = DATA_DIR / "codigos_postales_Madrid_centro.csv"
REFERENCE_CSV = PROJECT_DIR.parent / "catalogo_mercadona_cabo_palos.csv"
OUTPUT_CSV = DATA_DIR / "productos_madrid_centro.csv"
CHECKPOINT = DATA_DIR / "productos_madrid_centro_progreso.json"
ERROR_LOG = DATA_DIR / "productos_madrid_centro_errores.log"

URL_MERCADONA = "https://www.mercadona.es"
TIMEOUT_MS = 3000
DETAIL_TIMEOUT_MS = 3000
SCROLL_SETTLE_MS = 500

COLUMNS = [
    "cp",
    "categoria",
    "subcategoria",
    "nombre",
    "formato_y_precio_por_kilo",
    "precio_unidad",
]


def normalize_cp(value: Any) -> str:
    """Devuelve un CP de cinco caracteres, preservando ceros iniciales."""
    return str(value).strip().split(".")[0].zfill(5)


def normalize_price(value: Any) -> str:
    return re.sub(r"\s+", "", str(value).lower().replace("€", "")).replace(",", ".")


def format_head(value: Any) -> str:
    """Extrae el formato anterior a la barra de precio y normaliza espacios."""
    return " ".join(str(value).split("|")[0].strip().split())


def product_key(
    categoria: Any,
    subcategoria: Any,
    nombre: Any,
    formato: Any,
) -> tuple[str, str, str, str]:
    return (
        str(categoria).strip(),
        str(subcategoria).strip(),
        str(nombre).strip(),
        format_head(formato).casefold(),
    )


def load_cp_list() -> list[str]:
    if not CP_INPUT.is_file():
        raise FileNotFoundError(f"No existe el CSV de códigos postales: {CP_INPUT}")
    df = pd.read_csv(CP_INPUT, dtype={"codigo_postal": "string"}, encoding="utf-8-sig")
    if "codigo_postal" not in df:
        raise ValueError(f"Falta la columna codigo_postal en {CP_INPUT}")
    return list(dict.fromkeys(normalize_cp(cp) for cp in df["codigo_postal"].dropna()))


def load_reference() -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    if not REFERENCE_CSV.is_file():
        raise FileNotFoundError(f"No existe el CSV original de referencia: {REFERENCE_CSV}")
    reference_df = pd.read_csv(
        REFERENCE_CSV,
        dtype="string",
        encoding="utf-8-sig",
        keep_default_na=False,
    )
    missing = set(COLUMNS) - set(reference_df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en el CSV de referencia: {sorted(missing)}")
    reference: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in reference_df[COLUMNS].to_dict(orient="records"):
        key = product_key(
            row["categoria"], row["subcategoria"], row["nombre"],
            row["formato_y_precio_por_kilo"],
        )
        reference.setdefault(key, []).append(row)
    return reference


def load_existing_rows() -> set[tuple[str, str, str, str, str]]:
    if not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0:
        return set()
    existing: set[tuple[str, str, str, str, str]] = set()
    with OUTPUT_CSV.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != COLUMNS:
            raise ValueError(
                f"El CSV de salida debe tener estas columnas: {', '.join(COLUMNS)}"
            )
        for row in reader:
            key = product_key(
                row["categoria"], row["subcategoria"], row["nombre"],
                row["formato_y_precio_por_kilo"],
            )
            existing.add((row["cp"], *key))
    return existing


def ensure_output() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0:
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as file:
            csv.DictWriter(file, fieldnames=COLUMNS).writeheader()


def append_row(row: dict[str, Any]) -> None:
    with OUTPUT_CSV.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
        file.flush()
        os.fsync(file.fileno())


def load_checkpoint() -> set[str]:
    if not CHECKPOINT.exists():
        return set()
    try:
        data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("El checkpoint debe contener una lista de textos")
        return set(data)
    except (OSError, ValueError, json.JSONDecodeError):
        logging.exception("No se pudo cargar el checkpoint %s", CHECKPOINT)
        return set()


def save_checkpoint(done: set[str]) -> None:
    temporary = CHECKPOINT.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")
    temporary.replace(CHECKPOINT)


def task_key(cp: str, categoria: str, subcategoria: str) -> str:
    # JSON evita colisiones si una etiqueta contiene el separador.
    return json.dumps([cp, categoria, subcategoria], ensure_ascii=False)


def enter_postal_code(page, cp: str) -> str:
    page.goto(URL_MERCADONA, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    form = page.get_by_role("banner").locator("form")
    form.get_by_label("Código postal").fill(cp, timeout=TIMEOUT_MS)
    form.get_by_role("button", name="ENTRAR").click(timeout=TIMEOUT_MS)
    page.wait_for_function(
        """() => {
            const url = location.href.toLowerCase();
            const text = document.body?.innerText.toLowerCase() || '';
            return url.includes('tienda.mercadona.es') || url.includes('telecompra') ||
                   text.includes('el código postal no es correcto');
        }""",
        timeout=TIMEOUT_MS,
    )
    if page.get_by_text("El código postal no es correcto.", exact=True).count():
        return "INVALIDO"
    if "telecompra" in page.url.lower():
        return "SIN_SERVICIO"
    page.get_by_role("link", name="Categorías").wait_for(
        state="visible", timeout=TIMEOUT_MS
    )
    page.get_by_role("link", name="Categorías").click(timeout=TIMEOUT_MS)
    page.wait_for_url("**/categories**", wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    page.locator(".category-menu").wait_for(state="visible", timeout=TIMEOUT_MS)
    return "VALIDO"


def get_categories(page) -> list[str]:
    return page.locator(".category-menu > .category-menu__item").evaluate_all(
        "els => els.map(e => e.querySelector('.category-menu__header label')?.innerText.trim()).filter(Boolean)"
    )


def open_category(page, category: str) -> list[str]:
    page.get_by_role("button", name=category, exact=True).click(timeout=TIMEOUT_MS)
    return page.locator(".category-menu__item").evaluate_all(
        """(els, name) => {
            const item = els.find(e => e.querySelector('.category-menu__header label')?.innerText.trim() === name);
            return item ? [...item.querySelectorAll('button.category-item__link')]
                .map(button => button.innerText.trim()).filter(Boolean) : [];
        }""",
        category,
    )


def restore_category_view(page, category: str) -> None:
    if page.get_by_test_id("modal-close-button").count():
        page.get_by_test_id("modal-close-button").click(timeout=TIMEOUT_MS)
    page.get_by_role("link", name="Categorías").click(timeout=TIMEOUT_MS)
    page.wait_for_url("**/categories**", timeout=TIMEOUT_MS)
    page.get_by_role("button", name=category, exact=True).click(timeout=TIMEOUT_MS)


def extract_detail(page, cp: str, category: str, subcategory: str, fallback_name: str) -> dict[str, str]:
    info = page.get_by_test_id("private-product-detail-info")
    info.wait_for(state="visible", timeout=DETAIL_TIMEOUT_MS)
    name = info.locator("h1").inner_text(timeout=DETAIL_TIMEOUT_MS).strip() or fallback_name
    detail_format = " ".join(
        value.strip()
        for value in info.locator(".product-format span[aria-hidden='true']").all_inner_texts()
        if value.strip()
    )
    price = info.locator(".product-price__unit-price").inner_text(
        timeout=DETAIL_TIMEOUT_MS
    ).strip()
    return {
        "cp": cp,
        "categoria": category,
        "subcategoria": subcategory,
        "nombre": name,
        "formato_y_precio_por_kilo": detail_format,
        "precio_unidad": price,
    }


def process_subcategory(
    page,
    cp: str,
    category: str,
    subcategory: str,
    reference: dict[tuple[str, str, str, str], list[dict[str, str]]],
    existing: set[tuple[str, str, str, str, str]],
) -> int:
    print(f"      Abriendo subcategoría: {subcategory}", flush=True)
    page.get_by_role("button", name=subcategory, exact=True).click(timeout=TIMEOUT_MS)
    cards = page.locator("[data-testid='product-cell']")
    cards.first.wait_for(state="visible", timeout=TIMEOUT_MS)
    scroll = page.locator(".grid-layout__main-container")
    if scroll.count():
        scroll.evaluate("element => element.scrollTop = element.scrollHeight")
    page.wait_for_timeout(SCROLL_SETTLE_MS)
    count = cards.count()
    print(f"      Productos detectados: {count}", flush=True)
    written = 0

    for index in range(count):
        card = cards.nth(index)
        name = card.get_by_test_id("product-cell-name").inner_text(
            timeout=DETAIL_TIMEOUT_MS
        ).strip()
        format_text = " ".join(
            value.strip()
            for value in card.locator(
                ".product-format__size--cell span[aria-hidden='true']"
            ).all_inner_texts()
            if value.strip()
        )
        card_price = card.locator(".product-price__unit-price").inner_text(
            timeout=DETAIL_TIMEOUT_MS
        ).strip()
        key = product_key(category, subcategory, name, format_text)
        row_key = (cp, *key)
        if row_key in existing:
            print(f"        {index + 1}/{count}: ya está en salida; se omite", flush=True)
            continue

        candidates = reference.get(key, [])
        reference_match = next(
            (row for row in candidates
             if normalize_price(card_price) == normalize_price(row["precio_unidad"])),
            None,
        )
        if reference_match is not None:
            row = dict(reference_match)
            row["cp"] = cp
            append_row(row)
            existing.add(row_key)
            written += 1
            print(f"        {index + 1}/{count}: copiado de referencia", flush=True)
            continue

        if candidates:
            print(f"        {index + 1}/{count}: precio distinto; abriendo ficha", flush=True)
        button = card.get_by_test_id("open-product-detail")
        button.click(timeout=DETAIL_TIMEOUT_MS)
        row = extract_detail(page, cp, category, subcategory, name)
        append_row(row)
        row_key = (cp, *product_key(
            row["categoria"], row["subcategoria"], row["nombre"],
            row["formato_y_precio_por_kilo"],
        ))
        existing.add(row_key)
        written += 1
        page.get_by_test_id("modal-close-button").click(timeout=DETAIL_TIMEOUT_MS)
        page.get_by_test_id("private-product-detail-info").wait_for(
            state="detached", timeout=TIMEOUT_MS
        )
    return written


def main() -> int:
    logging.basicConfig(
        filename=ERROR_LOG,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    codes = load_cp_list()
    reference = load_reference()
    ensure_output()
    existing = load_existing_rows()
    done = load_checkpoint()
    print(
        f"Inicio: {len(codes)} CP de Madrid Centro; "
        f"{len(done)} tareas en checkpoint; {len(existing)} filas ya en salida.",
        flush=True,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        page.set_default_navigation_timeout(TIMEOUT_MS)
        try:
            for cp_position, cp in enumerate(codes, start=1):
                cp_complete = f"{cp}:COMPLETO"
                cp_invalid = f"{cp}:INVALIDO"
                cp_no_service = f"{cp}:SIN_SERVICIO"
                if any(item in done for item in (cp_complete, cp_invalid, cp_no_service)):
                    print(f"[{cp_position}/{len(codes)}] CP {cp}: ya comprobado; se omite", flush=True)
                    continue

                print(f"\n[{cp_position}/{len(codes)}] CP {cp}: iniciando", flush=True)
                try:
                    state = enter_postal_code(page, cp)
                    if state == "INVALIDO":
                        print(f"[{cp_position}/{len(codes)}] CP {cp} inválido; se omite", flush=True)
                        done.add(cp_invalid)
                        save_checkpoint(done)
                        continue
                    if state == "SIN_SERVICIO":
                        print(f"[{cp_position}/{len(codes)}] CP {cp} sin servicio; se omite", flush=True)
                        done.add(cp_no_service)
                        save_checkpoint(done)
                        continue

                    categories = get_categories(page)
                    print(f"[{cp_position}/{len(codes)}] Servicio disponible; {len(categories)} categorías", flush=True)
                    cp_had_error = False
                    for category_position, category in enumerate(categories, start=1):
                        print(f"  Categoría {category_position}/{len(categories)}: {category}", flush=True)
                        try:
                            subcategories = open_category(page, category)
                            if not subcategories:
                                cp_had_error = True
                                logging.warning("CP=%s categoría sin subcategorías: %s", cp, category)
                            for subcategory in subcategories:
                                key = task_key(cp, category, subcategory)
                                if key in done:
                                    print(f"    Subcategoría ya completada: {subcategory}", flush=True)
                                    continue
                                try:
                                    written = process_subcategory(
                                        page, cp, category, subcategory, reference, existing
                                    )
                                    done.add(key)
                                    save_checkpoint(done)
                                    print(f"      Subcategoría guardada; {written} filas nuevas", flush=True)
                                    restore_category_view(page, category)
                                except Exception:
                                    cp_had_error = True
                                    logging.exception(
                                        "Falló CP=%s categoría=%s subcategoría=%s",
                                        cp, category, subcategory,
                                    )
                                    print(f"      ERROR en {cp} / {category} / {subcategory}; revisar log", flush=True)
                                    try:
                                        restore_category_view(page, category)
                                    except Exception:
                                        logging.exception("No se pudo recuperar la vista de categoría para CP=%s", cp)
                                        break
                            # Cada iteración de categoría comienza desde su vista índice.
                            page.get_by_role("link", name="Categorías").click(timeout=TIMEOUT_MS)
                            page.wait_for_url("**/categories**", timeout=TIMEOUT_MS)
                        except Exception:
                            cp_had_error = True
                            logging.exception("Falló CP=%s categoría=%s", cp, category)
                            try:
                                page.goto("https://tienda.mercadona.es/categories", wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                            except Exception:
                                logging.exception("No se pudo recuperar el catálogo de CP=%s", cp)
                                break

                    if not cp_had_error:
                        done.add(cp_complete)
                        save_checkpoint(done)
                        print(f"[{cp_position}/{len(codes)}] CP {cp}: completo", flush=True)
                    else:
                        print(f"[{cp_position}/{len(codes)}] CP {cp}: parcial; se reanudará lo pendiente", flush=True)
                except PlaywrightTimeoutError:
                    logging.exception("Timeout procesando CP=%s", cp)
                    print(f"[{cp_position}/{len(codes)}] TIMEOUT CP {cp}; no se marca como completo", flush=True)
                except Exception:
                    logging.exception("Error procesando CP=%s", cp)
                    print(f"[{cp_position}/{len(codes)}] ERROR CP {cp}; no se marca como completo", flush=True)
        finally:
            try:
                browser.close()
            except Exception:
                logging.exception("Error al cerrar Chromium")
    print(f"Proceso terminado. CSV: {OUTPUT_CSV} | checkpoint: {CHECKPOINT} | log: {ERROR_LOG}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
