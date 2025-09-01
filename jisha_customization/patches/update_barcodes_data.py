import frappe

def execute():
    """Patch to copy data from custom_barcodes to custom_barcodes_v1 in Stock Entry Detail"""
    try:
        details = frappe.get_all(
            "Stock Entry Detail",
            filters={"custom_barcodes": ["!=", ""]},   # only rows with data
            fields=["name", "custom_barcodes"]
        )

        for d in details:
            frappe.db.set_value(
                "Stock Entry Detail",
                d.name,
                "custom_barcodes_v1",
                d.custom_barcodes,
                update_modified=False
            )

        frappe.logger().info(f"✅ Migrated {len(details)} Stock Entry Detail rows from custom_barcodes → custom_barcodes_v1")

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Patch: Copy custom_barcodes to custom_barcodes_v1")
        raise
