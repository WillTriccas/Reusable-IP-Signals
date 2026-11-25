from .orders import record_order
from .reports import export_orders


if __name__ == "__main__":
    receipt = record_order("SAMPLE-001", 2, 15)
    print(export_orders([receipt]), end="")
