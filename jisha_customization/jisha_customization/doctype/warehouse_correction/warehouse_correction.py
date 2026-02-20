# Copyright (c) 2026, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WarehouseCorrection(Document):
	pass


# @frappe.whitelist()
# def run_warehouse_correction(docname):
#     """
#     Executes warehouse correction from Custom Button
#     (Warehouse Correction is a Single Doctype)
#     """

#     doc = frappe.get_doc("Warehouse Correction", docname)

#     # 🛑 Prevent double execution
#     if doc.get("is_applied"):
#         frappe.throw(_("Warehouse correction has already been applied."))

#     if not doc.items:
#         frappe.throw(_("No Warehouse Correction Items found."))

#     barcode_updated = 0
#     box_updated = 0
#     error_count = 0
#     error_logs = []

#     for item in doc.items:
#         warehouse = item.warehouse
#         barcodes = _parse_list(item.barcodes)
#         box_refs = _parse_list(item.box_references)

#         if not warehouse or not barcodes:
#             continue

#         for barcode in barcodes:

#             # Barcode Entry name = barcode
#             if not frappe.db.exists("Barcode Entry", barcode):
#                 error_logs.append(
#                     f"Barcode Entry not found: {barcode}"
#                 )
#                 error_count += 1
#                 continue

#             # ✅ Update Barcode Entry
#             frappe.db.set_value(
#                 "Barcode Entry",
#                 barcode,
#                 "warehouse",
#                 warehouse,
#                 update_modified=False
#             )
#             barcode_updated += 1

#             for box_ref in box_refs:

#                 if not frappe.db.exists("Box Creation", box_ref):
#                     error_logs.append(
#                         f"Box Creation not found: {box_ref} "
#                         f"(Barcode: {barcode})"
#                     )
#                     error_count += 1
#                     continue

#                 child_rows = frappe.db.get_all(
#                     "Barcode Box",   # ⚠️ update if different
#                     filters={
#                         "parent": box_ref,
#                         "parenttype": "Box Creation",
#                         "barcode_reference": barcode
#                     },
#                     fields=["name"]
#                 )

#                 if not child_rows:
#                     error_logs.append(
#                         f"Barcode '{barcode}' not linked in "
#                         f"Box Creation '{box_ref}'"
#                     )
#                     error_count += 1
#                     continue

#                 for row in child_rows:
#                     frappe.db.set_value(
#                         "Barcode Box",
#                         row.name,
#                         "warehouse",
#                         warehouse,
#                         update_modified=False
#                     )
#                     box_updated += 1

#     # 🧾 Create ONE error log entry
#     if error_logs:
#         frappe.log_error(
#             title="Warehouse Correction Errors",
#             message="\n".join(error_logs)
#         )

#     # 🧾 Mark execution complete
#     frappe.db.set_value(
#         "Warehouse Correction",
#         doc.name,
#         {
#             "is_applied": 1
#         }
#     )

#     frappe.db.commit()

#     return {
#         "message": _(
#             f"Warehouse Correction completed successfully.<br>"
#             f"<b>Barcodes Updated:</b> {barcode_updated}<br>"
#             f"<b>Box Rows Updated:</b> {box_updated}<br>"
#             f"<b>Errors:</b> {error_count}"
#         )
#     }


# def _parse_list(value):
#     """
#     Converts multiline or comma-separated values
#     into a clean list
#     """
#     if not value:
#         return []

#     return [
#         v.strip()
#         for v in value.replace(",", "\n").split("\n")
#         if v.strip()
#     ]

@frappe.whitelist()
def run_warehouse_correction(docname):
    """
    Executes warehouse correction.
    Processes only unprocessed rows.
    """

    doc = frappe.get_doc("Warehouse Correction", docname)

    if not doc.items:
        frappe.throw(_("No Warehouse Correction Items found."))

    barcode_updated = 0
    box_updated = 0
    error_count = 0
    error_logs = []
    processed_rows = 0

    for item in doc.items:

        # ✅ Skip already processed rows
        if item.is_processed:
            continue

        warehouse = item.warehouse
        row_type = (item.type or "").strip()
        barcodes = _parse_list(item.barcodes)
        box_refs = _parse_list(item.box_references)

        if not warehouse:
            continue

        row_updated = False

        # =====================================================
        # TYPE = BARCODE
        # =====================================================
        if row_type == "Barcode":

            if not barcodes:
                error_logs.append(f"Row {item.idx}: No barcodes provided.")
                error_count += 1
                continue

            for barcode in barcodes:

                if not frappe.db.exists("Barcode Entry", barcode):
                    error_logs.append(f"Barcode Entry not found: {barcode}")
                    error_count += 1
                    continue

                frappe.db.set_value(
                    "Barcode Entry",
                    barcode,
                    "warehouse",
                    warehouse,
                    update_modified=False
                )

                barcode_updated += 1
                row_updated = True

        # =====================================================
        # TYPE = BOX
        # =====================================================
        elif row_type == "Box":

            if not box_refs:
                error_logs.append(f"Row {item.idx}: No Box References provided.")
                error_count += 1
                continue

            for box_ref in box_refs:

                if not frappe.db.exists("Box Creation", box_ref):
                    error_logs.append(f"Box Creation not found: {box_ref}")
                    error_count += 1
                    continue

                child_rows = frappe.db.get_all(
                    "Barcode Box",
                    filters={
                        "parent": box_ref,
                        "parenttype": "Box Creation"
                    },
                    fields=["name","barcode_reference"]
                )

                if not child_rows:
                    error_logs.append(
                        f"No Barcode rows found in Box Creation '{box_ref}'"
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

                    # If Barcode Entry name == child row name
                    if frappe.db.exists("Barcode Entry", row.barcode_reference):
                        frappe.db.set_value(
                            "Barcode Entry",
                            row.barcode_reference,
                            "warehouse",
                            warehouse,
                            update_modified=False
                        )

                    box_updated += 1
                    row_updated = True

        else:
            error_logs.append(f"Row {item.idx}: Invalid type '{row_type}'")
            error_count += 1

        # ✅ Mark row processed only if update happened
        if row_updated:
            frappe.db.set_value(
                item.doctype,
                item.name,
                "is_processed",
                1,
                update_modified=False
            )
            processed_rows += 1

    # 🧾 Log errors once
    if error_logs:
        frappe.log_error(
            title="Warehouse Correction Errors",
            message="\n".join(error_logs)
        )

    frappe.db.commit()

    return {
        "message": _(
            f"Warehouse Correction completed successfully.<br><br>"
            f"<b>Rows Processed:</b> {processed_rows}<br>"
            f"<b>Barcodes Updated:</b> {barcode_updated}<br>"
            f"<b>Box Rows Updated:</b> {box_updated}<br>"
            f"<b>Errors:</b> {error_count}"
        )
    }


def _parse_list(value):
    if not value:
        return []

    return [
        v.strip()
        for v in value.replace(",", "\n").split("\n")
        if v.strip()
    ]