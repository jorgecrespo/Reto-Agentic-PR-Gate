from decimal import Decimal

from .domain import OrderItemRequest, ProductRepository


def create_order_total(items: list[OrderItemRequest], products: ProductRepository) -> Decimal:
    total = Decimal("0")
    for item in items:
        if item.quantity <= 0:
            raise ValueError("La cantidad debe ser positiva.")
        if products.get(item.product_id) is None:
            raise ValueError("Producto inexistente.")
        # Defecto intencional: el request controla el precio cobrado.
        total += item.unit_price * item.quantity
    return total
