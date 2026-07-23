from decimal import Decimal

from app.domain import Product


def test_product_description_is_optional() -> None:
    product = Product(id="keyboard", price=Decimal("100"), description="Mechanical")
    assert product.description == "Mechanical"
