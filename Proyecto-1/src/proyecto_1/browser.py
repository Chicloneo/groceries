"""Recorrido del catálogo de Mercadona y exportación incremental a CSV.

La lista `lista_codigos_postales` debe existir en el entorno que invoca main(),
como iterable de CP; se conservan como texto para no perder ceros iniciales.
"""
import csv
import json
import logging
from pathlib import Path
import pandas as pd

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL_MERCADONA = "https://www.mercadona.es"
CP_REFERENCIA = "30370"
CSV_SALIDA = Path("catalogo_mercadona.csv")
ESTADO = Path("catalogo_mercadona_progreso.json")
LOG = Path("catalogo_mercadona_errores.log")
TIMEOUT = 3000
DETAIL_TIMEOUT = 3000
CAMPOS = ["cp", "categoria", "subcategoria", "nombre", "formato_y_precio_por_kilo", "precio_unidad"]

ROOT_DIR = Path(__file__).parent.parent.parent
DATA_FOLDER = ROOT_DIR / "Data"
DATA_PATH = DATA_FOLDER / "codigos_postales_municipios.csv"
df = pd.read_csv(DATA_PATH)
LISTA_CODIGOS_POSTALES = list(df["codigo_postal"])


def normalizar_cp(cp):
    return str(cp).strip().split(".")[0].zfill(5)


def cargar_estado():
    if ESTADO.exists():
        try:
            return set(json.loads(ESTADO.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            logging.exception("No se pudo leer el checkpoint %s", ESTADO)
    return set()


def guardar_estado(completados):
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(completados), ensure_ascii=False), encoding="utf-8")
    tmp.replace(ESTADO)


def append_rows(rows):
    if not rows:
        return
    nuevo = not CSV_SALIDA.exists() or CSV_SALIDA.stat().st_size == 0
    with CSV_SALIDA.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            writer.writeheader()
        writer.writerows(rows)


def entrar_cp(page, cp):
    page.goto(URL_MERCADONA, wait_until="domcontentloaded", timeout=TIMEOUT)
    form = page.get_by_role("banner").locator("form")
    form.get_by_label("Código postal").fill(cp)
    form.get_by_role("button", name="ENTRAR").click()
    # CP inexistente muestra un error inline y no navega; servicio/no servicio
    # producen una URL de destino. Esperamos cualquiera de esos resultados.
    page.wait_for_function("""() => {
        const u = location.href.toLowerCase();
        const body = document.body?.innerText.toLowerCase() || '';
        return u.includes('tienda.mercadona.es') || u.includes('telecompra') ||
               body.includes('el código postal no es correcto');
    }""", timeout=5000)
    if page.get_by_text("El código postal no es correcto.", exact=True).count():
        return "INVALIDO"
    if "telecompra" in page.url.lower():
        return "SIN_SERVICIO"
    page.get_by_role("link", name="Categorías").wait_for(state="visible", timeout=TIMEOUT)
    page.get_by_role("link", name="Categorías").click()
    page.wait_for_url("**/categories**", wait_until="domcontentloaded", timeout=TIMEOUT)
    page.locator(".category-menu").wait_for(state="visible", timeout=TIMEOUT)
    return True


def sidebar_categories(page):
    return page.locator(".category-menu > .category-menu__item").evaluate_all(
        "els => els.map(e => e.querySelector('.category-menu__header label')?.innerText.trim()).filter(Boolean)"
    )


def abrir_categoria(page, nombre):
    page.get_by_role("button", name=nombre, exact=True).click()
    return page.locator(".category-menu__item").evaluate_all(
        """(els, nombre) => {
            const item = els.find(e => e.querySelector('.category-menu__header label')?.innerText.trim() === nombre);
            return item ? [...item.querySelectorAll('button.category-item__link')].map(b => b.innerText.trim()).filter(Boolean) : [];
        }""", nombre)


# API manual original: se conserva para ejecutar el flujo de un solo CP/producto.
def introducir_CP(page, cp):
    page.goto(URL_MERCADONA, wait_until="domcontentloaded", timeout=TIMEOUT)
    form = page.get_by_role("banner").locator("form")
    form.get_by_label("Código postal").fill(cp)
    form.get_by_role("button", name="ENTRAR").click()
    page.wait_for_url(lambda u: "tienda.mercadona.es" in u.lower() or "telecompra" in u.lower(), timeout=TIMEOUT)
    return page, page.url


def wait_images(page):
    container = page.locator(".grid-layout__main-container")
    if container.count():
        container.evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_function("""() => [...document.querySelectorAll('.product-cell__image-wrapper img')]
        .every(img => img.complete && img.naturalWidth > 0)""", timeout=TIMEOUT)
    return page


def entrar_en_categorias(page):
    page.get_by_role("link", name="Categorías").click()
    page.wait_for_url("**/categories**", timeout=TIMEOUT)
    return page


def entrar_a_categoria(page, categoria):
    abrir_categoria(page, categoria)
    return page


def entrar_a_subcategoria(page, subcategoria):
    page.get_by_role("button", name=subcategoria, exact=True).click()
    return page


def entrar_a_producto(page, producto):
    page.get_by_role("button", name=producto).click()
    page.get_by_test_id("private-product-detail-info").wait_for(state="visible", timeout=TIMEOUT)
    return page


def obtener_datos_producto(page):
    info = page.get_by_test_id("private-product-detail-info")
    return {
        "nombre": info.locator("h1").inner_text().strip(),
        "formato_y_precio_por_kilo": " ".join(x.strip() for x in info.locator(
            ".product-format span[aria-hidden='true']").all_inner_texts() if x.strip()),
        "precio_unidad": info.get_by_test_id("product-price").inner_text().strip(),
    }


def clave_producto(categoria, subcategoria, nombre, formato):
    # El formato detallado de la ficha añade "| €/kg"; la tarjeta no.
    formato = formato.split("|")[0].strip().lower()
    return (categoria.strip(), subcategoria.strip(), nombre.strip(), " ".join(formato.split()))


def precio_normalizado(precio):
    return "".join(str(precio).lower().replace("€", "").split()).replace(",", ".")


def obtener_productos_subcategoria(page, cp, categoria, subcategoria, referencia=None):
    print(f"      Abriendo subcategoría: {subcategoria}", flush=True)
    page.get_by_role("button", name=subcategoria, exact=True).click()
    page.locator("[data-testid='product-cell']").first.wait_for(state="visible", timeout=TIMEOUT)
    # La inspección aportada encontró el scroll en este contenedor y todas las
    # 43 tarjetas presentes antes/después del recorrido en esa subcategoría.
    page.locator(".grid-layout__main-container").evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(500)
    cards = page.locator("[data-testid='product-cell']")
    total = cards.count()
    print(f"      Productos detectados: {total}", flush=True)
    rows = []
    for i in range(total):
        print(f"        Producto {i + 1}/{total}", flush=True)
        card = cards.nth(i)
        name = card.get_by_test_id("product-cell-name").inner_text().strip()
        card_format = " ".join(x.strip() for x in card.locator(
            ".product-format__size--cell span[aria-hidden='true']").all_inner_texts() if x.strip())
        card_price = card.locator(".product-price__unit-price").inner_text().strip()
        key = clave_producto(categoria, subcategoria, name, card_format)
        ref = referencia.get(key) if referencia is not None else None
        # En CP no referencia, si nombre+formato y precio coinciden, copiamos
        # la fila de referencia cambiando solo el CP; evitamos abrir el detalle.
        if ref and precio_normalizado(card_price) == precio_normalizado(ref["precio_unidad"]):
            fila = dict(ref)
            fila["cp"] = cp
            rows.append(fila)
            print(f"        Producto {i + 1}/{total}: coincide con referencia; detalle omitido", flush=True)
            continue
        if ref:
            print(f"        Producto {i + 1}/{total}: precio distinto; abriendo ficha", flush=True)
        elif referencia is not None:
            print(f"        Producto {i + 1}/{total}: nuevo en este CP; abriendo ficha", flush=True)
        button = card.get_by_test_id("open-product-detail")
        button.click()
        info = page.get_by_test_id("private-product-detail-info")
        try:
            info.wait_for(state="visible", timeout=DETAIL_TIMEOUT)
        except PlaywrightTimeoutError:
            # La navegación del detalle puede tardar más que la validación de CP.
            # Un segundo clic no es seguro: podría cerrar una ficha que haya
            # terminado de abrirse justo al vencer la primera espera.
            raise RuntimeError(
                f"No apareció la ficha del producto {i + 1}/{total}: {name}; "
                "se deja la subcategoría sin checkpoint para reintentarla"
            )
        fmt = " ".join(x.strip() for x in info.locator(
            ".product-format span[aria-hidden='true']").all_inner_texts() if x.strip())
        # Puede haber precio anterior y precio rebajado, ambos con el mismo
        # test id. El precio vigente usa esta clase en el HTML de la ficha.
        price = info.locator(".product-price__unit-price").inner_text().strip()
        fila = {"cp": cp, "categoria": categoria, "subcategoria": subcategoria,
                     "nombre": info.locator("h1").inner_text().strip() or name,
                     "formato_y_precio_por_kilo": fmt, "precio_unidad": price}
        rows.append(fila)
        if referencia is not None:
            referencia[clave_producto(categoria, subcategoria, fila["nombre"], card_format or fmt)] = fila
        page.get_by_test_id("modal-close-button").click()
        info.wait_for(state="detached", timeout=TIMEOUT)
    return rows

def main(lista_codigos_postales=LISTA_CODIGOS_POSTALES):
    if lista_codigos_postales is None:
        try:
            lista_codigos_postales = globals()["lista_codigos_postales"]
        except KeyError as e:
            raise RuntimeError("Define lista_codigos_postales como iterable de CP antes de llamar main().") from e
    logging.basicConfig(filename=LOG, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    completados = cargar_estado()
    codigos = [normalizar_cp(cp) for cp in lista_codigos_postales]
    if CP_REFERENCIA in codigos:
        codigos.remove(CP_REFERENCIA)
    codigos.insert(0, CP_REFERENCIA)
    referencia = {}
    if CSV_SALIDA.exists():
        with CSV_SALIDA.open("r", newline="", encoding="utf-8-sig") as f:
            for fila in csv.DictReader(f):
                if fila.get("cp") == CP_REFERENCIA:
                    referencia[clave_producto(fila["categoria"], fila["subcategoria"], fila["nombre"], fila["formato_y_precio_por_kilo"])] = fila
    total_cp = len(codigos)
    print(f"Inicio de extracción: {total_cp} códigos postales; "
          f"{len(completados)} tareas ya constan en el checkpoint.", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            for pos_cp, cp in enumerate(codigos, start=1):
                print(f"\n[{pos_cp}/{total_cp}] CP {cp}: iniciando", flush=True)
                try:
                    estado_cp = entrar_cp(page, cp)
                    if estado_cp == "INVALIDO":
                        print(f"[{pos_cp}/{total_cp}] CP {cp} inválido; se omite.", flush=True)
                        completados.add(f"{cp}:INVALIDO")
                        guardar_estado(completados)
                        continue
                    if estado_cp == "SIN_SERVICIO":
                        print(f"[{pos_cp}/{total_cp}] El Código Postal {cp} no tiene Mercadona", flush=True)
                        completados.add(f"{cp}:SIN_SERVICIO")
                        guardar_estado(completados)
                        continue
                    cats = sidebar_categories(page)
                    print(f"[{pos_cp}/{total_cp}] Servicio disponible; {len(cats)} categorías detectadas.", flush=True)
                    for pos_cat, cat in enumerate(cats, start=1):
                        print(f"  Categoría {pos_cat}/{len(cats)}: {cat}", flush=True)
                        try:
                            subs = abrir_categoria(page, cat)
                            if not subs:
                                # No se inventan subcategorías ni se marca como completado.
                                logging.warning("CP=%s categoría sin subcategorías visibles: %s", cp, cat)
                            for sub in subs:
                                key = f"{cp}:{cat}:{sub}"
                                if key in completados:
                                    print(f"    Subcategoría ya completada; se omite: {sub}", flush=True)
                                    continue
                                try:
                                    rows = obtener_productos_subcategoria(
                                        page, cp, cat, sub,
                                        referencia=None if cp == CP_REFERENCIA else referencia,
                                    )
                                    append_rows(rows)
                                    if cp == CP_REFERENCIA:
                                        for fila in rows:
                                            referencia[clave_producto(fila["categoria"], fila["subcategoria"], fila["nombre"], fila["formato_y_precio_por_kilo"])] = fila
                                    completados.add(key)
                                    guardar_estado(completados)
                                    print(f"      Guardados {len(rows)} productos. CSV actualizado.", flush=True)
                                except Exception:
                                    print(f"      ERROR en {cp} / {cat} / {sub}; detalle en {LOG}", flush=True)
                                    logging.exception("Falló CP=%s categoría=%s subcategoría=%s", cp, cat, sub)
                                    close_modal = page.get_by_test_id("modal-close-button")
                                    if close_modal.count():
                                        close_modal.click(timeout=5000)
                                        page.get_by_test_id("private-product-detail-info").wait_for(
                                            state="detached", timeout=5000
                                        )
                                # Volver al índice de categorías y abrir el siguiente item.
                                page.get_by_role("link", name="Categorías").click()
                                page.wait_for_url("**/categories**", wait_until="domcontentloaded", timeout=TIMEOUT)
                                page.get_by_role("button", name=cat, exact=True).click()
                        except Exception:
                            logging.exception("Falló CP=%s categoría=%s", cp, cat)
                            try:
                                page.get_by_role("link", name="Categorías").click()
                                page.wait_for_url("**/categories**", timeout=TIMEOUT)
                            except Exception:
                                page.goto("https://tienda.mercadona.es/categories", wait_until="domcontentloaded")
                    completados.add(f"{cp}:COMPLETO")
                    guardar_estado(completados)
                    print(f"[{pos_cp}/{total_cp}] CP {cp}: terminado.", flush=True)
                except PlaywrightTimeoutError:
                    print(f"[{pos_cp}/{total_cp}] TIMEOUT en CP {cp}; detalle en {LOG}", flush=True)
                    logging.exception("Timeout procesando CP=%s", cp)
                except Exception:
                    print(f"[{pos_cp}/{total_cp}] ERROR en CP {cp}; detalle en {LOG}", flush=True)
                    logging.exception("Falló CP=%s", cp)
        finally:
            browser.close()
            print(f"Proceso finalizado. CSV: {CSV_SALIDA.resolve()} | progreso: {ESTADO.resolve()} | errores: {LOG.resolve()}", flush=True)


if __name__ == "__main__":
    main()
