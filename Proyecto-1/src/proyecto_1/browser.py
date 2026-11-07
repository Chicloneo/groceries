from playwright.sync_api import sync_playwright, TimeoutError

CP = "28005"
URL_MERCADONA = "https://www.mercadona.es"
CATEGORIA = "Aperitivos"
SUB_CATEGORIA = "Patatas fritas y snacks"
PRODUCTO = "Patatas fritas onduladas Hacendado"

def introducir_CP(page, cp:str=CP):
    """Introducir código postal en la primera página de Mercadona"""

    print(f"\n {page.title()} \n")
    print(f"Estamos en {page.url}")
    page.screenshot(path="Screenshots/1_pantalla_inicial.png")

    form = page.get_by_role("banner").locator("form")
    form.get_by_label("Código postal").fill(cp)
    form.get_by_role("button", name="ENTRAR").click()

    try:
        # IA, pero la idea la tengo clara
        page.wait_for_url(
            lambda url: (
                "tienda.mercadona.es" in url.lower()
                or "telecompra" in url.lower()
            ),
            wait_until="domcontentloaded",
            timeout=30000,
            )
    except TimeoutError as te:
        print(f"Error de conexión: {te}")

    print(f"Hemos entrado a la tienda de Mercadona: {page.url} con el CP: {cp}")
    page.screenshot(path="Screenshots/2_tienda.png")

    url = page.url

    return page, url

def wait_images(page):

    # Esperamos a  que las imágenes se carguen. Nos desplazamos por la página. 
    # Hay que parecer lo más humano posible.
    # Código con IA
    page.evaluate("""
        async () => {
            const paso = Math.max(300, window.innerHeight * 0.75);
            for (let y = 0; y < document.body.scrollHeight; y += paso) {
                window.scrollTo(0, y);
                await new Promise(resolve => setTimeout(resolve, 250));
            }
            window.scrollTo(0, 0);
        }
    """)
    page.wait_for_function("""
        () => {
            const imgs = [...document.querySelectorAll(
                ".product-cell__image-wrapper img"
            )];
            return imgs.length > 0 &&
                   imgs.every(img => img.complete && img.naturalWidth > 0);
        }
    """, timeout=60000)

    return page

def entrar_en_categorias(page):

    page.get_by_role("link", name="Categorías").click()
    page.wait_for_url("**/tienda**") #buscamos "tienda" en cualquier parte de la url

    page = wait_images(page)

    print(f"Hemos entrado al catálogo: {page.url}")
    page.screenshot(path="Screenshots/3_categorias.png")

    return page

def entrar_a_categoria(page, categoria:str=CATEGORIA):

    page.get_by_role("button", name=categoria, exact=True).click()
    page.wait_for_load_state("domcontentloaded") #IA. Aün no entiendo qué hace

    page = wait_images(page)
    print(f"Hemos entrado a la categoría {categoria}: {page.url}")
    page.screenshot(path=f"Screenshots/4_{categoria}.png")

    return page

def entrar_a_subcategoria(page, subcategoria:str=SUB_CATEGORIA):

    page.get_by_role("button", name=subcategoria, exact=True).click()

    page = wait_images(page)
    print(f"Hemos entrado a la subcategoria {SUB_CATEGORIA}: {page.url}")
    page.screenshot(path=f"Screenshots/5_{subcategoria}.png")

    return page

def entrar_a_producto(page, producto:str=PRODUCTO):

    page.get_by_role("button", name=producto).click()

    page = wait_images(page)
    print(f"Hemos entrado al producto {PRODUCTO}: {page.url}")
    page.screenshot(path=f"Screenshots/6_{producto}.png")

    return page

def obtener_datos_producto(page):

    info = page.get_by_test_id("private-product-detail-info")

    # IA
    datos = {
        "nombre": info.locator("h1").inner_text(),
        "formato_y_precio_por_kilo": info.locator(
            ".product-format span[aria-hidden='true']"
        ).all_inner_texts(),
        "precio_unidad": info.get_by_test_id("product-price").inner_text(),
    }

    print(datos)

    return page


def main():

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL_MERCADONA)

        page, url = introducir_CP(page)

        if 'telecompra' not in url:
            page = entrar_en_categorias(page)
            page = entrar_a_categoria(page)
            page = entrar_a_subcategoria(page)
            page = entrar_a_producto(page)
            page = obtener_datos_producto(page)
        else:
            #El Código Postal no tiene Mercadona
            print(f"El Código Postal {CP} no tiene Mercadona")

        browser.close()

if __name__ == "__main__":
    main()