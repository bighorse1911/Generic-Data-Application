import logging
import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("generator_relational")


# --------- Data shapes (dataclasses) ---------
@dataclass(frozen=True)
class CustomerRow:
    customer_id: int
    full_name: str
    email: str
    created_at: str


@dataclass(frozen=True)
class OrderRow:
    order_id: int
    customer_id: int
    order_date: str
    status: str


@dataclass(frozen=True)
class OrderItemRow:
    order_item_id: int
    order_id: int
    sku: str
    quantity: int
    unit_price: float


@dataclass(frozen=True)
class RelationalData:
    customers: list[CustomerRow]
    orders: list[OrderRow]
    order_items: list[OrderItemRow]


# --------- Small vocab lists ---------
FIRST_NAMES = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Jamie", "Avery"]
LAST_NAMES = ["Smith", "Nguyen", "Khan", "Brown", "Garcia", "Wilson", "Chen", "Patel", "Martin"]
ORDER_STATUS = ["NEW", "PAID", "SHIPPED", "CANCELLED"]

SKU_PREFIXES = ["AUS", "NZX", "DEV", "LAB", "KIT", "PRO"]
SKU_SUFFIXES = ["01", "02", "03", "10", "11", "20", "30"]


def _random_email(full_name: str, rng: random.Random) -> str:
    base = full_name.lower().replace(" ", ".")
    suffix = "".join(rng.choices(string.ascii_lowercase + string.digits, k=3))
    domain = rng.choice(["example.com", "mail.test", "demo.local"])
    return f"{base}.{suffix}@{domain}"


def _iso_utc(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def generate_relational_data(
    *,
    num_customers: int,
    orders_per_customer_min: int,
    orders_per_customer_max: int,
    items_per_order_min: int,
    items_per_order_max: int,
    seed: int = 0,
) -> RelationalData:
    """
    Generates relational data with valid PK/FK links:
      customers (customer_id)
      orders (order_id, customer_id -> customers.customer_id)
      order_items (order_item_id, order_id -> orders.order_id)

    All output is deterministic for the same seed + inputs.
    """
    # ---- Validate inputs (good practice) ----
    if num_customers <= 0:
        raise ValueError("num_customers must be > 0")
    if orders_per_customer_min <= 0 or orders_per_customer_max <= 0:
        raise ValueError("orders_per_customer_min/max must be > 0")
    if orders_per_customer_min > orders_per_customer_max:
        raise ValueError("orders_per_customer_min cannot exceed max")
    if items_per_order_min <= 0 or items_per_order_max <= 0:
        raise ValueError("items_per_order_min/max must be > 0")
    if items_per_order_min > items_per_order_max:
        raise ValueError("items_per_order_min cannot exceed max")

    rng = random.Random(seed)

    # Deterministic base time so unit tests and repeatability are stable
    base_time = datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(
        seconds=rng.randint(0, 10_000_000)
    )

    customers: list[CustomerRow] = []
    orders: list[OrderRow] = []
    items: list[OrderItemRow] = []

    order_id = 1
    order_item_id = 1

    # ---- Customers ----
    for customer_id in range(1, num_customers + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        full_name = f"{first} {last}"

        created_at = _iso_utc(base_time - timedelta(days=rng.randint(0, 365)))

        cust = CustomerRow(
            customer_id=customer_id,
            full_name=full_name,
            email=_random_email(full_name, rng),
            created_at=created_at,
        )
        customers.append(cust)

        # ---- Orders for this customer ----
        num_orders = rng.randint(orders_per_customer_min, orders_per_customer_max)
        for _ in range(num_orders):
            order_date = _iso_utc(base_time - timedelta(days=rng.randint(0, 365)))
            status = rng.choice(ORDER_STATUS)

            ord_row = OrderRow(
                order_id=order_id,
                customer_id=customer_id,  # FK to customers
                order_date=order_date,
                status=status,
            )
            orders.append(ord_row)

            # ---- Items for this order ----
            num_items = rng.randint(items_per_order_min, items_per_order_max)
            for _ in range(num_items):
                sku = f"{rng.choice(SKU_PREFIXES)}-{rng.randint(100, 999)}-{rng.choice(SKU_SUFFIXES)}"
                quantity = rng.randint(1, 5)
                unit_price = round(rng.uniform(5.0, 250.0), 2)

                items.append(
                    OrderItemRow(
                        order_item_id=order_item_id,
                        order_id=order_id,  # FK to orders
                        sku=sku,
                        quantity=quantity,
                        unit_price=unit_price,
                    )
                )
                order_item_id += 1

            order_id += 1

    logger.info(
        "Generated relational data: customers=%d, orders=%d, order_items=%d (seed=%d)",
        len(customers), len(orders), len(items), seed
    )

    return RelationalData(customers=customers, orders=orders, order_items=items)
