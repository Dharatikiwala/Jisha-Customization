# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return as make_si_return

class ReturnBarcodeVoucher(Document):
	pass


@frappe.whitelist()
def get_barcode_data(barcode_data):
	# First check if barcode exists in Barcode Entry
	barcode_entry = frappe.db.exists("Barcode Entry", barcode_data)
	if barcode_entry:
		doc = frappe.get_doc("Barcode Entry", barcode_data)
		if doc.status == "Delivered" and (doc.reference_of_sales_invoice or doc.reference_of_delivery_note):
			return doc
		else:
			return {
				"status": "error", 
				"message": "Only Delivered barcode should be scanned."
			}
	
	box_creation = frappe.db.exists("Box Creation", barcode_data)
	if box_creation:
		doc = frappe.get_doc("Box Creation", barcode_data)
		if doc.reference_of_sales_invoice or doc.reference_of_delivery_note:
			return doc
		else:
			return {
				"status": "error", 
				"message": f"Barcode '{barcode_data}' is not associated with any sales."
			}
	
	# If not found in either, return a proper error message
	return {"status": "error", "message": f"Barcode '{barcode_data}' not found"}




@frappe.whitelist()
def make_voucher_return(items):
	try:
		items = json.loads(items)
		results = []
		
		if items:
			for item in items:
				sales_invoice_reference = item.get("sales_invoice_reference")
				delivery_note_reference = item.get("delivery_note_reference")
				result = {}
				
				if sales_invoice_reference:
					# Fetch the original Sales Invoice
					sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_reference)
					# frappe.throw(str(sales_invoice.name))

					return_si_doc = frappe.db.get_value("Sales Invoice",{"is_return":1,"return_against":sales_invoice_reference},"name")
					if return_si_doc:
						return_exists = frappe.db.get_all("Sales Invoice Item", filters={"parent": return_si_doc, "item_code": item.get("item_code"), "qty": -item.get("quantity")}, fields=["name"])
						# Check if a return already exists for the same item and quantity
						if return_exists:
							frappe.throw(f"A return already exists for Item {item.get('item_code')} with Quantity {item.get('quantity')} in Sales Invoice {return_si_doc}.")
							return				
					# Create a new Sales Invoice for return
					return_doc = make_si_return(sales_invoice_reference)
					return_doc.items = [
						return_si_item
						for return_si_item in return_doc.items
						if return_si_item.item_code == item.get("item_code")
					]
					for return_si_item in return_doc.items:
						return_si_item.custom_box_creation_reference = item.get("box_creation_reference", "") if abs(return_si_item.qty) == abs(item.get("quantity")) else ""
						return_si_item.qty = -item.get("quantity")
						return_si_item.custom_barcodes = item.get("barcodes")
							
					return_doc.run_method("calculate_taxes_and_totals")
					return_doc.save()
					return_doc.submit()
					frappe.log_error("return doc",return_doc.as_dict())
	
					frappe.db.set_value("Returned Barcode Table", {"parent":item.get("parent"),"sales_invoice_reference":sales_invoice.name}, "returned_sales_invoice", return_doc.name)
					frappe.db.commit()
					
					result = {
						"status": "success",
						"message": f"Return Sales Invoice {return_doc.name} created successfully."
					}

				elif delivery_note_reference:
					# Fetch the original Delivery Note
					delivery_note = frappe.get_doc("Delivery Note", delivery_note_reference)


					return_dn_doc = frappe.db.get_value("Delivery Note",{"is_return":1,"return_against":delivery_note_reference},"name")
					if return_dn_doc:
						return_exists = frappe.db.get_all("Delivery Note Item", filters={"parent": return_dn_doc, "item_code": item.get("item_code"), "qty": -item.get("quantity"),"custom_barcodes":item.get("barcodes")}, fields=["name"])
						# Check if a return already exists for the same item and quantity
						if return_exists:
							frappe.throw(f"A return already exists for Item {item.get('item_code')} with Quantity {item.get('quantity')} in Delivery Note {return_dn_doc}.")
							return	
					
					# Create a new Delivery Note for return
					return_doc = make_sales_return(delivery_note_reference)
					return_doc.items = [
						return_dn_item
						for return_dn_item in return_doc.items
						if return_dn_item.item_code == item.get("item_code")
					]
					for return_dn_item in return_doc.items:
						return_dn_item.qty = -item.get("quantity")
						return_dn_item.custom_barcodes = item.get("barcodes")
						return_dn_item.custom_box_creation_reference = item.get("box_creation_reference", "") if abs(return_dn_item.qty) == abs(item.get("quantity")) else ""
					return_doc.run_method("calculate_taxes_and_totals")
					return_doc.save()
					return_doc.submit()

					for dn_item in delivery_note.items:
						if dn_item.item_code == item.get("item_code"):
							# Get current returned_qty or initialize to 0 if None
							current_returned_qty = dn_item.returned_qty or 0
							# Add the returned quantity and update directly using set_value
							new_returned_qty = current_returned_qty + item.get("quantity")
							frappe.db.set_value("Delivery Note Item",{"name":dn_item.name,"item_code":item.get("item_code")},"returned_qty",new_returned_qty)
							# break
					
					total_qty = sum([abs(dni.qty) for dni in delivery_note.items if dni.qty])
					total_returned_qty = sum([
						abs(frappe.db.get_value("Delivery Note Item", dni.name, "returned_qty") or 0)
						for dni in delivery_note.items
					])

					per_returned = (total_returned_qty / total_qty) * 100 if total_qty else 0

					# Update per_returned in Delivery Note
					frappe.db.set_value("Delivery Note", delivery_note.name, "per_returned", per_returned)

					frappe.db.set_value("Returned Barcode Table", {"parent":item.get("parent"),"delivery_note_reference": delivery_note_reference}, "returned_delivery_note", return_doc.name)
					frappe.db.commit()

					result = {
						"status": "success",
						"message": f"Return Delivery Note {return_doc.name} created successfully."
					}		
				
				if result:
					results.append(result)
			
			if results:
				frappe.msgprint("\n".join([result.get("message") for result in results]))
				return results[0] if len(results) == 1 else {"status": "success", "message": f"Created {len(results)} return documents", "results": results}
		
		return {"status": "error", "message": "No valid sales invoice or delivery note reference found in items."}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Return Voucher Creation Error")
		return {"status": "error", "message": f"An error occurred: {str(e)}"}