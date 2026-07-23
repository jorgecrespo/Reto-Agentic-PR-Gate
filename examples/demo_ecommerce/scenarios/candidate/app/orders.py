from decimal import Decimal

from .domain import OrderItemRequest, ProductRepository


def create_order_total(items: list[OrderItemRequest], products: ProductRepository) -> Decimal:
    total = Decimal("0")
    for item in items:
        if item.quantity <= 0:
            raise ValueError("La cantidad debe ser positiva.")
        product = products.get(item.product_id)
        if product is None:
            raise ValueError("Producto inexistente.")
        total += product.price * item.quantity
    return total
