import csv
import io


def export_orders(orders):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["order_id", "total"])
    writer.writerows(orders)
    return output.getvalue()
