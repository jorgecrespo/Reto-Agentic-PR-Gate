from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    id: str
    price: Decimal


@dataclass(frozen=True)
class OrderItemRequest:
    product_id: str
    quantity: int
    unit_price: Decimal


class ProductRepository:
    def __init__(self, products: list[Product]) -> None:
        self._products = {product.id: product for product in products}

    def get(self, product_id: str) -> Product | None:
        return self._products.get(product_id)
