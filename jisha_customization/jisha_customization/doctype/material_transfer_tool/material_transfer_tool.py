# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
import re

class MaterialTransferTool(Document):
	pass


@frappe.whitelist()
def get_material_requests(item_code,branch):

	return frappe.db.sql("""
		SELECT
			mr.name AS material_request,
			mr.transaction_date,
			mri.name AS material_request_item,
			(mri.qty - mri.ordered_qty) AS qty,
			mri.item_code,
			mri.warehouse,
			mri.branch
		FROM
			`tabMaterial Request Item` mri
		INNER JOIN
			`tabMaterial Request` mr ON mr.name = mri.parent
		WHERE
			mri.item_code = %s
			AND mr.custom_requested_by_branch = %s
			AND mr.docstatus = 1
			AND mr.status IN ('Pending', 'Partially Received')
			AND (mri.qty - mri.ordered_qty) > 0
	""", (item_code,branch), as_dict=1)


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
		elif doc.status == "Active" and doc.reference_of_box:
			return {
				"status": "error",
				"message": f"Barcode '{barcode_data}' is already assigned to Box {doc.reference_of_box}. Please scan only unassigned barcodes."
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

@frappe.whitelist()
def create_mt(items,branch):
	try:
		if not branch:
			frappe.throw("To Branch is required to create Material Transfer.")
			
		items = json.loads(items or "[]")

		if not items:
			frappe.throw("No item data found for Material Transfer creation.")

		# ✅ Check if today's draft Stock Entry already exists
		stock_entry = frappe.db.get_value(
			"Stock Entry",
			{
				"posting_date": frappe.utils.today(),
				"stock_entry_type": "Material Transfer",
				"docstatus": 0,   # Draft
				"custom_branch":branch
			},
			"name"
		)

		if stock_entry:
			# Load existing draft
			stock_doc = frappe.get_doc("Stock Entry", stock_entry)
			stock_doc.custom_branch = branch
		else:
			# Create new draft Stock Entry
			stock_doc = frappe.new_doc("Stock Entry")
			stock_doc.update({
				"posting_date": frappe.utils.today(),
				"stock_entry_type": "Material Transfer",
				"custom_branch":branch
			})

		# ✅ Check duplicates first
		for item in items:
			exists = frappe.db.exists(
				"Stock Entry Detail",
				{
					"item_code": item.get("item_code"),
					"s_warehouse": item.get("source_warehouse"),
					"t_warehouse": item.get("target_warehouse"),
					"batch_no": item.get("batch"),
					"qty": item.get("barcode_qty"),
					"custom_is_created_from_mt_tool":1,
					"material_request": item.get("material_request"),
					"material_request_item": item.get("material_request_item"),
					"parent": stock_doc.name if stock_doc.name else None,
					"parenttype": "Stock Entry",
				},
			)

			if exists:
				return {
					"status": "error",
					"message": (
						f"Duplicate entry detected: Item {frappe.bold(item.get('item_code'))} "
						f"(Batch {frappe.bold(item.get('batch'))}, Qty {frappe.bold(item.get('barcode_qty'))}) "
						f"already exists in Stock Entry {frappe.bold(stock_doc.name)}."
					)
				}

		# ✅ Append new items
		for item in items:
			stock_doc.append("items", {
				"item_code": item.get("item_code"),
				"s_warehouse": item.get("source_warehouse"),
				"t_warehouse": item.get("target_warehouse"),
				"batch_no": item.get("batch"),
				"qty": item.get("barcode_qty"),
				"custom_is_created_from_mt_tool":1,
				"material_request": item.get("material_request"),
				"material_request_item": item.get("material_request_item"),
				"custom_barcodes_v1": item.get("barcodes"),
				"custom_box_reference": item.get("boxes"),
				"branch": item.get("to_branch")
			})

		# Save (insert if new, update if existing)
		stock_doc.calculate_rate_and_amount()
		stock_doc.save(ignore_permissions=True)

		return {"status": "success", "message": f"Material Transfer {stock_doc.name} updated successfully."}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Material Transfer Creation Failed")
		return {"status": "error", "message": f"Failed to create Material Transfer: {str(e)}"}
