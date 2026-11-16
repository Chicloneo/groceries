"""Presentación del ticket final por consola."""

from decimal import Decimal
from types import SimpleNamespace

from proyecto_2.shopping_cli import _show_ticket


def test_ticket_shows_unit_prices_line_totals_and_basket_total(capsys):
    product = SimpleNamespace(original_text="8 L de leche semidesnatada")
    session = SimpleNamespace(
        request=SimpleNamespace(products=[product]),
        searches=[
            {
                "options": [
                    {
                        "option_id": "producto-1-opcion-1",
                        "product": {
                            "nombre": "Leche semidesnatada Asturiana",
                            "formato": "Brik 1 L",
                            "precio": 1.09,
                        },
                    }
                ]
            }
        ],
        selections={0: {"producto-1-opcion-1": 2}},
        product_totals={0: Decimal("2.18")},
        total_price=Decimal("2.18"),
    )

    _show_ticket(session)

    output = capsys.readouterr().out
    assert "1.09 €/unidad" in output
    assert "2.18 €" in output
    assert "Subtotal: 2.18 €" in output
    assert "TOTAL: 2.18 €" in output
