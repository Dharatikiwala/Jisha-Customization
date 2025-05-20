# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BoxCreation(Document):
	def on_submit(self):
		# frappe.throw("on submit event")
		if self.table_mrql:
			barcodes = [item.barcode_reference for item in self.table_mrql]
			frappe.db.set_value("Barcode Entry", {"name": ["in", barcodes]}, "reference_of_box", self.name)
	
	def on_cancel(self):
		if self.table_mrql:
			barcodes = [item.barcode_reference for item in self.table_mrql]
			frappe.db.set_value("Barcode Entry", {"name": ["in", barcodes]}, "reference_of_box", "")



@frappe.whitelist()
def get_barcode_entry(qty,batch_no=None, stock_entry=None):
	
	if batch_no:
		batch_entries = frappe.get_all("Barcode Entry", filters={"batch": batch_no, "reference_of_box": ["is", "not set"]}, fields=["*"], order_by='name asc')
		batch_count = len(batch_entries)
		if int(qty) > batch_count:
			frappe.throw(f"Batch {batch_no} has only {batch_count} entries available in Barcode Entry Document.")
		
		# Map the barcodes with the quantity
		mapped_barcodes = batch_entries[:int(qty)]
		return mapped_barcodes
	if stock_entry:
		stock_entry_entries = frappe.get_all("Barcode Entry", filters={"reference_of_manufacturing_entry": stock_entry, "reference_of_box": ["is", "not set"]}, fields=["*"], order_by='name asc')
		stock_entry_count = len(stock_entry_entries)
		if int(qty) > stock_entry_count:
			frappe.throw(f"Stock Entry {stock_entry} has only {stock_entry_count} entries available in Barcode Entry Document.")
		
		# Map the barcodes with the quantity
		mapped_barcodes = stock_entry_entries[:int(qty)]
		return mapped_barcodes