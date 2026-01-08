# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
    make_sales_return as make_si_return,
)


class ReturnBarcodeVoucher(Document):
	def on_cancel(self):
		if self.returned_items:
			for item in self.returned_items:
				try:
					if item.returned_delivery_note:
						frappe.get_doc("Delivery Note", item.returned_delivery_note).cancel()
					
					if item.returned_sales_invoice:
						frappe.get_doc("Sales Invoice", item.returned_sales_invoice).cancel()
				except Exception as e:
					frappe.log_error(frappe.get_traceback(), "Return Voucher Cancellation Error")
					frappe.throw(f"Error canceling return documents: {str(e)}")


@frappe.whitelist()
def get_barcode_data(barcode_data):
    # First check if barcode exists in Barcode Entry
    barcode_entry = frappe.db.exists("Barcode Entry", barcode_data)
    if barcode_entry:
        doc = frappe.get_doc("Barcode Entry", barcode_data)
        if doc.status == "Delivered" and (
            doc.reference_of_sales_invoice or doc.reference_of_delivery_note
        ):
            return doc
        else:
            return {
                "status": "error",
                "message": "Only Delivered barcode should be scanned.",
            }

    box_creation = frappe.db.exists("Box Creation", barcode_data)
    if box_creation:
        doc = frappe.get_doc("Box Creation", barcode_data)
        if doc.reference_of_sales_invoice or doc.reference_of_delivery_note:
            return doc
        else:
            return {
                "status": "error",
                "message": f"Barcode '{barcode_data}' is not associated with any sales.",
            }

    # If not found in either, return a proper error message
    return {"status": "error", "message": f"Barcode '{barcode_data}' not found"}


@frappe.whitelist()
def make_voucher_return(items):
    try:
        items = json.loads(items)
        results = []

        if not items:
            return {"status": "error", "message": "No items provided."}

        for item in items:
            parent = item.get("parent")

            # 1️⃣ DELIVERY NOTE RETURN FIRST
            if item.get("delivery_note_reference"):
                dn_result = _create_delivery_note_return(item, parent)
                if dn_result:
                    results.append(dn_result)

            # 2️⃣ SALES INVOICE RETURN SECOND
            if item.get("sales_invoice_reference"):
                si_result = _create_sales_invoice_return(item, parent)
                if si_result:
                    results.append(si_result)

        if results:
            frappe.msgprint("\n".join(r["message"] for r in results))
            return {
                "status": "success",
                "message": f"{len(results)} return document(s) created",
                "results": results,
            }

        return {"status": "error", "message": "No return documents created."}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Return Voucher Creation Error")
        return {"status": "error", "message": str(e)}


def _normalize_multivalue(value, separator):
    """
    Converts multi-value text field into a normalized set
    """
    if not value:
        return set()
    return {
        v.strip()
        for v in value.split(separator)
        if v and v.strip()
    }


def _match_barcodes_and_boxes(row_barcodes, row_box_ref, input_barcodes, input_box_ref):
    """
    Safe comparison for Long Text barcodes and comma-separated box refs
    """
    row_barcodes_set = _normalize_multivalue(row_barcodes, "\n")
    input_barcodes_set = _normalize_multivalue(input_barcodes, "\n")

    row_box_set = _normalize_multivalue(row_box_ref, ",")
    input_box_set = _normalize_multivalue(input_box_ref, ",")

    return row_barcodes_set == input_barcodes_set and row_box_set == input_box_set

def _create_delivery_note_return(item, parent):
    item_code = item.get("item_code")
    batch_no = item.get("batch_no")
    qty = item.get("quantity") or 0
    barcodes = item.get("barcodes") or ""
    box_ref = item.get("box_creation_reference") or ""
    dn_ref = item.get("delivery_note_reference")

    delivery_note = frappe.get_doc("Delivery Note", dn_ref)

    # 🔒 Idempotency check (Python-level for Long Text)
    existing_return = frappe.db.get_value(
        "Delivery Note",
        {"is_return": 1, "return_against": dn_ref},
        "name",
    )

    if existing_return:
        return_items = frappe.get_all(
            "Delivery Note Item",
            filters={"parent": existing_return, "item_code": item_code,"batch_no":batch_no},
            fields=["custom_barcodes", "custom_box_creation_reference", "qty"],
        )

        for r in return_items:
            if (
                r.qty == -qty
                and _match_barcodes_and_boxes(
                    r.custom_barcodes,
                    r.custom_box_creation_reference,
                    barcodes,
                    box_ref,
                )
            ):
                frappe.throw(
                    f"A return already exists for Item {item.get('item_code')} "
                    f"with same Barcodes & Box reference in Delivery Note {existing_return}."
                )

    # ✅ Create DN return
    return_doc = make_sales_return(dn_ref)

    # ⚠️ DN does NOT copy custom fields → filter ONLY by item_code
    return_doc.items = [
        d for d in return_doc.items if d.item_code == item_code and d.batch_no == batch_no
    ]

    if not return_doc.items:
        frappe.throw(f"No matching Delivery Note item for {item_code}")

    for d in return_doc.items:
        d.qty = -qty
        d.custom_barcodes = barcodes
        d.custom_box_creation_reference = box_ref

    return_doc.run_method("calculate_taxes_and_totals")
    return_doc.save()
    return_doc.submit()

    # 🔄 Update returned_qty accurately
    for d in delivery_note.items:
        if (
            d.item_code == item_code
            and d.batch_no == batch_no
            and _match_barcodes_and_boxes(
                d.custom_barcodes,
                d.custom_box_creation_reference,
                barcodes,
                box_ref,
            )
        ):
            frappe.db.set_value(
                "Delivery Note Item",
                d.name,
                "returned_qty",
                (d.returned_qty or 0) + qty,
            )

    # 🔄 Update per_returned
    total_qty = sum(abs(d.qty) for d in delivery_note.items if d.qty)
    total_returned = sum(
        abs(
            frappe.db.get_value(
                "Delivery Note Item", d.name, "returned_qty"
            )
            or 0
        )
        for d in delivery_note.items
    )

    frappe.db.set_value(
        "Delivery Note",
        dn_ref,
        "per_returned",
        (total_returned / total_qty) * 100 if total_qty else 0,
    )

    # ✅ Set return reference (your logic)
    frappe.db.set_value(
        "Returned Barcode Table",
        {"parent": parent, "delivery_note_reference": dn_ref},
        "returned_delivery_note",
        return_doc.name,
    )

    frappe.db.commit()

    return {
        "status": "success",
        "message": f"Return Delivery Note {return_doc.name} created.",
    }

def _create_sales_invoice_return(item, parent):
    item_code = item.get("item_code")
    batch_no = item.get("batch_no")
    qty = item.get("quantity") or 0
    barcodes = item.get("barcodes") or ""
    box_ref = item.get("box_creation_reference") or ""
    si_ref = item.get("sales_invoice_reference")

    existing_return = frappe.db.get_value(
        "Sales Invoice",
        {"is_return": 1, "return_against": si_ref},
        "name",
    )

    if existing_return:
        return_items = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": existing_return, "item_code": item_code,"batch_no":batch_no},
            fields=["custom_barcodes", "custom_box_creation_reference", "qty"],
        )

        for r in return_items:
            if (
                r.qty == -qty
                and _match_barcodes_and_boxes(
                    r.custom_barcodes,
                    r.custom_box_creation_reference,
                    barcodes,
                    box_ref,
                )
            ):
                frappe.throw(
                    f"A return already exists for Item {item.get('item_code')} "
                    f"with same Barcodes & Box reference in Sales Invoice {existing_return}."
                )

    return_doc = make_si_return(si_ref)

    # SI copies custom fields → safe to match fully
    return_doc.items = [
        s
        for s in return_doc.items
        if (
            s.item_code == item_code
            and s.batch_no == batch_no
            and _match_barcodes_and_boxes(
                s.custom_barcodes,
                s.custom_box_creation_reference,
                barcodes,
                box_ref,
            )
        )
    ]

    if not return_doc.items:
        frappe.throw(f"No matching Sales Invoice item for {item_code}")

    for s in return_doc.items:
        s.qty = -qty
        s.custom_barcodes = barcodes
        s.custom_box_creation_reference = box_ref

    # 🔕 Avoid outstanding warning
    return_doc.update_outstanding_for_self = 0

    return_doc.run_method("calculate_taxes_and_totals")
    return_doc.save()
    return_doc.submit()

    frappe.db.set_value(
        "Returned Barcode Table",
        {"parent": parent, "sales_invoice_reference": si_ref},
        "returned_sales_invoice",
        return_doc.name,
    )

    frappe.db.commit()

    return {
        "status": "success",
        "message": f"Return Sales Invoice {return_doc.name} created.",
    }
