# Copyright (c) 2026, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from frappe.utils import flt

class JishaStockScanner(Document):
	pass


@frappe.whitelist()
def get_barcode_data(barcode_data):
	# First check if barcode exists in Barcode Entry
	barcode_entry = frappe.db.exists("Barcode Entry", barcode_data)
	if barcode_entry:
		doc = frappe.get_doc("Barcode Entry", barcode_data)
		warning = None
		# Check if either reference_of_sales_invoice or reference_of_delivery_note is not empty
		if doc.status == "Delivered" and (doc.reference_of_sales_invoice or doc.reference_of_delivery_note):
			# Determine which reference(s) exist for the warning message
			if doc.reference_of_sales_invoice:
				warning = f"Barcode '{barcode_data}' is already associated with sales invoice {doc.reference_of_sales_invoice}"
			else:
				warning = f"Barcode '{barcode_data}' is already associated with a delivery note {doc.reference_of_delivery_note}"
		
		doc_dict = doc.as_dict()
		if warning:
			doc_dict["warning"] = warning
		return doc_dict
	
	box_creation = frappe.db.exists("Box Creation", barcode_data)
	if box_creation:
		doc = frappe.get_doc("Box Creation", barcode_data)
		warning = None
		# Check if either reference_of_sales_invoice or reference_of_delivery_note is not empty
		if doc.reference_of_sales_invoice or doc.reference_of_delivery_note:
			# Determine which reference(s) exist for the warning message
			if doc.reference_of_sales_invoice:
				warning = f"Box Creation '{barcode_data}' is already associated with sales invoice {doc.reference_of_sales_invoice}"
			else:
				warning = f"Box Creation '{barcode_data}' is already associated with a delivery note {doc.reference_of_delivery_note}"
		
		doc_dict = doc.as_dict()
		doc_dict["table_mrql"] = [d.as_dict() for d in doc.table_mrql]
		if warning:
			doc_dict["warning"] = warning
		return doc_dict
	
	# If not found in either, return a proper error message
	return {"status": "error", "message": f"Barcode/Box '{barcode_data}' not found"}


@frappe.whitelist()
def get_batch_valuation_rate(item_code, warehouse, batch_no):
	if not item_code or not warehouse or not batch_no:
		return 0.0

	# batch_no could contain multiple batches separated by newlines
	batches = [b.strip() for b in batch_no.split("\n") if b.strip()]
	if not batches:
		return 0.0

	from erpnext.stock.report.batch_wise_balance_history.batch_wise_balance_history import get_stock_ledger_entries

	today = frappe.utils.today()
	company = frappe.db.get_value("Warehouse", warehouse, "company")

	filters = frappe._dict({
		"from_date": today,
		"to_date": today,
		"item_code": item_code,
		"warehouse": warehouse,
		"company": company
	})

	try:
		entries = get_stock_ledger_entries(filters)
	except Exception as e:
		frappe.log_error(f"Error fetching stock ledger entries for batch: {str(e)}", "Jisha Stock Scanner")
		entries = []

	total_qty = 0.0
	total_val_diff = 0.0

	for d in entries:
		if d.get("batch_no") and d.get("batch_no").strip() in batches:
			total_qty += flt(d.get("actual_qty"))
			total_val_diff += flt(d.get("stock_value_difference"))

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


@frappe.whitelist()
def get_item_stock_details(item_code, warehouse, batch_no):
	if not item_code or not warehouse:
		return {"warehouse_qty": 0.0, "batch_valuation_rate": 0.0}
	
	warehouse_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0.0
	batch_valuation_rate = get_batch_valuation_rate(item_code, warehouse, batch_no)
	
	return {
		"warehouse_qty": warehouse_qty,
		"batch_valuation_rate": batch_valuation_rate
	}


@frappe.whitelist()
def create_stock_audit(doc):
	try:
		doc = json.loads(doc or "{}")

		if not doc:
			frappe.throw("No data found for Stock Audit creation.")

		items = doc.get("items") or []
		if not items:
			frappe.throw("No items found for Stock Audit creation.")

		# Group items by their Target Warehouse (row.warehouse)
		items_by_target_warehouse = {}
		for item in items:
			target_wh = item.get("warehouse")
			barcode_qty = item.get("barcode_qty") or 0
			if not target_wh:
				frappe.throw(f"Target Warehouse is missing for item {item.get('item_code')}.")
			if barcode_qty <= 0:
				continue  # skip items with 0 qty
			
			if target_wh not in items_by_target_warehouse:
				items_by_target_warehouse[target_wh] = []
			items_by_target_warehouse[target_wh].append(item)

		if not items_by_target_warehouse:
			return {
				"status": "error",
				"message": "No items with barcode quantity greater than 0 found."
			}

		created_audits = []

		for target_wh, target_items in items_by_target_warehouse.items():
			# Get or create today's Draft Stock Audit for target_wh
			stock_audit_name = frappe.db.get_value(
				"Stock Audit",
				{
					"date": frappe.utils.today(),
					"warehouse": target_wh,
					"docstatus": 0,
				},
				"name"
			)

			if stock_audit_name:
				stock_audit_doc = frappe.get_doc("Stock Audit", stock_audit_name)
			else:
				stock_audit_doc = frappe.new_doc("Stock Audit")
				stock_audit_doc.date = frappe.utils.today()
				stock_audit_doc.warehouse = target_wh
				stock_audit_doc.user = frappe.session.user

			# Overwrite items list for this target warehouse Stock Audit
			stock_audit_doc.items = []

			for item in target_items:
				item_code = item.get("item_code")
				system_wh = item.get("system_warehouse")
				batch_no = item.get("batch")
				barcode_qty = item.get("barcode_qty") or 0

				# Read qty & valuation rate directly from the scanned item row to optimize performance for 1000+ items
				warehouse_qty = flt(item.get("warehouse_qty") or 0.0)
				batch_valuation_rate = flt(item.get("batch_valuation_rate") or 0.0)
				variance_qty = warehouse_qty - barcode_qty

				stock_audit_doc.append("items", {
					"item_code": item_code,
					"barcode_qty": barcode_qty,
					"warehouse_qty": warehouse_qty,
					"variance_qty": variance_qty,
					"batch": batch_no,
					"barcodes": item.get("barcodes"),
					"boxes": item.get("boxes"),
					"custom_batch_valuation_rate": batch_valuation_rate
				})

			stock_audit_doc.save(ignore_permissions=True)
			created_audits.append(stock_audit_doc.name)

		return {
			"status": "success",
			"message": f"Draft Stock Audit(s) created/updated successfully: {', '.join(created_audits)}"
		}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Stock Audit Creation Failed")
		return {
			"status": "error",
			"message": f"Failed to create/update Stock Audit: {str(e)}"
		}








