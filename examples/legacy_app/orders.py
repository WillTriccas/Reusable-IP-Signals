import sqlite3

from .pricing import calculate_total


def record_order(order_id, quantity, unit_price):
    total = calculate_total(quantity, unit_price)
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE orders (id TEXT, total REAL)")
        connection.execute("INSERT INTO orders VALUES (?, ?)", (order_id, total))
        return connection.execute(
            "SELECT id, total FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
