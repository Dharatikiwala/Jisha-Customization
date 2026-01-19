# Copyright (c) 2026, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WarehouseCorrection(Document):
	pass


@frappe.whitelist()
def run_warehouse_correction(docname):
    """
    Executes warehouse correction from Custom Button
    (Warehouse Correction is a Single Doctype)
    """

    doc = frappe.get_doc("Warehouse Correction", docname)

    # 🛑 Prevent double execution
    if doc.get("is_applied"):
        frappe.throw(_("Warehouse correction has already been applied."))

    if not doc.items:
        frappe.throw(_("No Warehouse Correction Items found."))

    barcode_updated = 0
    box_updated = 0
    error_count = 0
    error_logs = []

    for item in doc.items:
        warehouse = item.warehouse
        barcodes = _parse_list(item.barcodes)
        box_refs = _parse_list(item.box_references)

        if not warehouse or not barcodes:
            continue

        for barcode in barcodes:

            # Barcode Entry name = barcode
            if not frappe.db.exists("Barcode Entry", barcode):
                error_logs.append(
                    f"Barcode Entry not found: {barcode}"
                )
                error_count += 1
                continue

            # ✅ Update Barcode Entry
            frappe.db.set_value(
                "Barcode Entry",
                barcode,
                "warehouse",
                warehouse,
                update_modified=False
            )
            barcode_updated += 1

            for box_ref in box_refs:

                if not frappe.db.exists("Box Creation", box_ref):
                    error_logs.append(
                        f"Box Creation not found: {box_ref} "
                        f"(Barcode: {barcode})"
                    )
                    error_count += 1
                    continue

                child_rows = frappe.db.get_all(
                    "Barcode Box",   # ⚠️ update if different
                    filters={
                        "parent": box_ref,
                        "parenttype": "Box Creation",
                        "barcode_reference": barcode
                    },
                    fields=["name"]
                )

                if not child_rows:
                    error_logs.append(
                        f"Barcode '{barcode}' not linked in "
                        f"Box Creation '{box_ref}'"
                    )
                    error_count += 1
                    continue

                for row in child_rows:
                    frappe.db.set_value(
                        "Barcode Box",
                        row.name,
                        "warehouse",
                        warehouse,
                        update_modified=False
                    )
                    box_updated += 1

    # 🧾 Create ONE error log entry
    if error_logs:
        frappe.log_error(
            title="Warehouse Correction Errors",
            message="\n".join(error_logs)
        )

    # 🧾 Mark execution complete
    frappe.db.set_value(
        "Warehouse Correction",
        doc.name,
        {
            "is_applied": 1
        }
    )

    frappe.db.commit()

    return {
        "message": _(
            f"Warehouse Correction completed successfully.<br>"
            f"<b>Barcodes Updated:</b> {barcode_updated}<br>"
            f"<b>Box Rows Updated:</b> {box_updated}<br>"
            f"<b>Errors:</b> {error_count}"
        )
    }


def _parse_list(value):
    """
    Converts multiline or comma-separated values
    into a clean list
    """
    if not value:
        return []

    return [
        v.strip()
        for v in value.replace(",", "\n").split("\n")
        if v.strip()
    ]

