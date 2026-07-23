from decimal import Decimal

from app.domain import OrderItemRequest, Product, ProductRepository
from app.orders import create_order_total


def test_uses_catalog_price_not_client_price() -> None:
    products = ProductRepository([Product(id="keyboard", price=Decimal("100"))])
    total = create_order_total(
        [OrderItemRequest(product_id="keyboard", quantity=2, unit_price=Decimal("1"))], products
    )
    assert total == Decimal("200")
