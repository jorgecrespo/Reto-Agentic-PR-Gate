from decimal import Decimal

import pytest

from app.domain import OrderItemRequest, Product, ProductRepository
from app.orders import create_order_total


def test_uses_catalog_price_not_client_price() -> None:
    products = ProductRepository([Product(id="keyboard", price=Decimal("100"))])
    total = create_order_total(
        [OrderItemRequest(product_id="keyboard", quantity=2, unit_price=Decimal("1"))], products
    )
    assert total == Decimal("200")


def test_rejects_unknown_product() -> None:
    with pytest.raises(ValueError, match="Producto inexistente"):
        create_order_total(
            [OrderItemRequest(product_id="missing", quantity=1, unit_price=Decimal("1"))],
            ProductRepository([]),
        )


def test_rejects_non_positive_quantity() -> None:
    with pytest.raises(ValueError, match="cantidad debe ser positiva"):
        create_order_total(
            [OrderItemRequest(product_id="keyboard", quantity=0, unit_price=Decimal("1"))],
            ProductRepository([Product(id="keyboard", price=Decimal("100"))]),
        )
