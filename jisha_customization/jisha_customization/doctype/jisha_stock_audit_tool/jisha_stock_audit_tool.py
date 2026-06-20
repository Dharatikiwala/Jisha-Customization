# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json

class JishaStockAuditTool(Document):
	pass



@frappe.whitelist()
def get_items(warehouse):
	return frappe.db.sql("""
		SELECT
			b.item_code,
			b.actual_qty
		FROM
			`tabBin` b
		JOIN
			`tabItem` i ON b.item_code = i.name
		WHERE
			b.warehouse = %s
			AND b.actual_qty > 0
			AND i.has_batch_no = 1
		Group BY
			b.item_code
	""", warehouse, as_dict=1)


@frappe.whitelist()
def get_barcode_data(barcode_data):
	# First check if barcode exists in Barcode Entry
	barcode_entry = frappe.db.exists("Barcode Entry", barcode_data)
	if barcode_entry:
		doc = frappe.get_doc("Barcode Entry", barcode_data)
		# Check if either reference_of_sales_invoice or reference_of_delivery_note is not empty
		if doc.status == "Delivered" and (doc.reference_of_sales_invoice or doc.reference_of_delivery_note):
			# Determine which reference(s) exist for the error message
			if doc.reference_of_sales_invoice:
				return {
					"status": "error", 
					"message": f"Barcode '{barcode_data}' is already associated with  sales invoice {doc.reference_of_sales_invoice}"
				}
			else:
				return {
					"status": "error", 
					"message": f"Barcode '{barcode_data}' is already associated with a delivery note {doc.reference_of_delivery_note}"
				}
		else:
			return doc
	
	box_creation = frappe.db.exists("Box Creation", barcode_data)
	if box_creation:
		doc = frappe.get_doc("Box Creation", barcode_data)
		# Check if either reference_of_sales_invoice or reference_of_delivery_note is not empty
		if doc.reference_of_sales_invoice or doc.reference_of_delivery_note:
			# Determine which reference(s) exist for the error message
			if doc.reference_of_sales_invoice:
				return {
					"status": "error", 
					"message": f"Box Creation '{barcode_data}' is already associated with both sales invoice {doc.reference_of_sales_invoice}"
				}
			else:
				return {
					"status": "error", 
					"message": f"Box Creation '{barcode_data}' is already associated with a delivery note {doc.reference_of_delivery_note}"
				}
		else:
			return doc
	
	# If not found in either, return a proper error message
	return {"status": "error", "message": f"Barcode '{barcode_data}' not found"}


# @frappe.whitelist()
# def create_stock_audit(doc):
# 	try:
# 		doc = json.loads(doc or "[]")

# 		if not doc:
# 			frappe.throw("No data found for Stock Audit creation.")

# 		# ✅ Check if today's draft Stock Entry already exists
# 		stock_audit = frappe.db.get_value(
# 			"Stock Audit",
# 			{
# 				"date": frappe.utils.today(),
# 				"warehouse": doc.get("warehouse"),
# 				"docstatus": 0,   # Draft
# 			},
# 			"name"
# 		)
# 		if stock_audit:
# 			# If exists, fetch the document
# 			stock_audit_doc = frappe.get_doc("Stock Audit", stock_audit)
# 		else:
# 			# If not, create a new Stock Entry document
# 			stock_audit_doc = frappe.new_doc("Stock Audit")
# 			stock_audit_doc.date = frappe.utils.today()
# 			stock_audit_doc.warehouse = doc.get("warehouse")
# 			stock_audit_doc.user = frappe.session.user
			
# 		for item in doc.get("items"):
# 			exists = frappe.db.exists(
# 				"Stock Audit Item",
# 				{
# 					"item_code": item.get("item_code"),
# 					"batch": item.get("batch"),
# 					"variance_qty": item.get("variance_qty"),
# 					"warehouse_qty": item.get("warehouse_qty"),
# 					"barcode_qty": item.get("barcode_qty"),
# 					"parent": stock_audit_doc.name if stock_audit_doc.name else None,
# 					"parenttype": "Stock Audit",
# 				},
# 			)

# 			if exists:
# 				existing_date = frappe.db.get_value("Stock Audit", stock_audit_doc.name, "date")
# 				if str(existing_date) == str(frappe.utils.today()):
# 					return {
# 						"status": "error",
# 						"message": (
# 							f"Duplicate entry detected: Item {frappe.bold(item.get('item_code'))} "
# 							f"(Batch {frappe.bold(item.get('batch'))}, Qty {frappe.bold(item.get('barcode_qty'))}) "
# 							f"already exists in Stock Audit {frappe.bold(stock_audit_doc.name)} "
# 							f"for date {frappe.bold(existing_date)}."
# 						)
# 					}

# 		has_items = False
# 		# ✅ Append new items
# 		for item in doc.get("items"):
# 			if item.get("barcode_qty") > 0:
# 				has_items = True
# 				stock_audit_doc.append("items", {
# 					"item_code": item.get("item_code"),
# 					"barcode_qty": item.get("barcode_qty"),
# 					"warehouse_qty": item.get("warehouse_qty"),
# 					"variance_qty": item.get("variance_qty"),
# 					"barcode_qty": item.get("barcode_qty"),
# 					"batch": item.get("batch"),
# 					"barcodes": item.get("barcodes"),
# 					"boxes": item.get("boxes")

# 				})
		
# 		if not has_items:
# 			return {
# 				"status": "error",
# 				"message": "No items with barcode quantity greater than 0 found. Stock Audit cannot be created/updated."
# 			}

# 		# Save (insert if new, update if existing)
# 		stock_audit_doc.save(ignore_permissions=True)

# 		return {"status": "success", "message": f"Stock Audit {stock_audit_doc.name} updated successfully."}	
# 	except Exception as e:
# 		frappe.db.rollback()
# 		frappe.log_error(frappe.get_traceback(), "Stock Audit Creation Failed")
# 		return {"status": "error", "message": f"Failed to create Stock Audit: {str(e)}"}


@frappe.whitelist()
def create_stock_audit(doc):
	try:
		doc = json.loads(doc or "{}")

		if not doc:
			frappe.throw("No data found for Stock Audit creation.")

		warehouse = doc.get("warehouse")
		items = doc.get("items") or []
		if not warehouse:
			frappe.throw("Warehouse is required.")
		if not items:
			frappe.throw("No items found for Stock Audit creation.")

		# Get or create Stock Audit for today (Draft)
		stock_audit_name = frappe.db.get_value(
			"Stock Audit",
			{
				"date": frappe.utils.today(),
				"warehouse": warehouse,
				"docstatus": 0,
			},
			"name"
		)

		if stock_audit_name:
			stock_audit_doc = frappe.get_doc("Stock Audit", stock_audit_name)
		else:
			stock_audit_doc = frappe.new_doc("Stock Audit")
			stock_audit_doc.date = frappe.utils.today()
			stock_audit_doc.warehouse = warehouse
			stock_audit_doc.user = frappe.session.user

		has_items = False
		# Reset stock audit doc items list so we overwrite with the scanned items
		stock_audit_doc.items = []

		for item in items:
			barcode_qty = item.get("barcode_qty") or 0
			if barcode_qty <= 0:
				continue  # skip items with 0 qty

			has_items = True
			stock_audit_doc.append("items", {
				"item_code": item.get("item_code"),
				"barcode_qty": barcode_qty,
				"warehouse_qty": item.get("warehouse_qty") or 0,
				"variance_qty": item.get("variance_qty") or 0,
				"batch": item.get("batch"),
				"barcodes": item.get("barcodes"),
				"boxes": item.get("boxes"),
				"custom_batch_valuation_rate": item.get("batch_valuation_rate") or 0.0
			})

		if not has_items:
			return {
				"status": "error",
				"message": "No items with barcode quantity greater than 0 found. Stock Audit cannot be created/updated."
			}

		# Save (insert or update)
		stock_audit_doc.save(ignore_permissions=True)

		return {
			"status": "success",
			"message": f"Stock Audit {stock_audit_doc.name} updated successfully."
		}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Stock Audit Creation Failed")
		return {
			"status": "error",
			"message": f"Failed to create/update Stock Audit: {str(e)}"
		}


@frappe.whitelist()
def get_batch_valuation_rate(item_code, warehouse, batch_no):
	if not item_code or not warehouse or not batch_no:
		return 0.0

	# batch_no could contain multiple batches separated by newlines
	batches = [b.strip() for b in batch_no.split("\n") if b.strip()]
	if not batches:
		return 0.0

	from frappe.utils import flt

	# 1. Fetch stock ledger entries with batch_no directly (non-bundle or legacy)
	sle_entries = frappe.db.sql("""
		SELECT
			SUM(actual_qty) AS qty,
			SUM(stock_value_difference) AS val_diff
		FROM
			`tabStock Ledger Entry`
		WHERE
			item_code = %s
			AND warehouse = %s
			AND batch_no IN %s
			AND docstatus < 2
			AND is_cancelled = 0
	""", (item_code, warehouse, batches), as_dict=True)

	# 2. Fetch bundle-based entries (serial and batch entry joined with stock ledger entry)
	bundle_entries = frappe.db.sql("""
		SELECT
			SUM(sbe.qty) AS qty,
			SUM(sbe.stock_value_difference) AS val_diff
		FROM
			`tabStock Ledger Entry` sle
		INNER JOIN
			`tabSerial and Batch Entry` sbe ON sbe.parent = sle.serial_and_batch_bundle
		WHERE
			sle.item_code = %s
			AND sle.warehouse = %s
			AND sbe.batch_no IN %s
			AND sle.docstatus < 2
			AND sle.is_cancelled = 0
	""", (item_code, warehouse, batches), as_dict=True)

	total_qty = 0.0
	total_val_diff = 0.0

	if sle_entries and sle_entries[0].qty:
		total_qty += flt(sle_entries[0].qty)
		total_val_diff += flt(sle_entries[0].val_diff)

	if bundle_entries and bundle_entries[0].qty:
		total_qty += flt(bundle_entries[0].qty)
		total_val_diff += flt(bundle_entries[0].val_diff)

	if total_qty > 0:
		return flt(total_val_diff / total_qty)

	# Fallback to standard valuation rate
	from erpnext.stock.stock_ledger import get_valuation_rate
	try:
		return get_valuation_rate(
			item_code=item_code,
			warehouse=warehouse,
			voucher_type="Stock Audit",
			voucher_no="Stock Audit",
			allow_zero_rate=True,
			raise_error_if_no_rate=False
		) or 0.0
	except Exception:
		return 0.0