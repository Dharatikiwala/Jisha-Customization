# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
import re

class BarcodeEntry(Document):
	# def on_trash(self):
	# 	if self.reference_of_manufacturing_entry and self.item_code:
	# 		filters = {
	# 			"parent": self.reference_of_manufacturing_entry,
	# 			"item_code": self.item_code
	# 		}
	# 		if self.batch:
	# 			filters["batch_no"] = self.batch

	# 		# Find matching Stock Entry Detail rows
	# 		stock_details = frappe.get_all(
	# 			"Stock Entry Detail",
	# 			filters=filters,
	# 			pluck="name"   # just get names
	# 		)

	# 		for detail_name in stock_details:
	# 			frappe.db.set_value(
	# 				"Stock Entry Detail",
	# 				detail_name,
	# 				"custom_barcodes_v1",
	# 				""   # clear the field completely
	# 			)
    
	def on_trash(self):
		if self.reference_of_manufacturing_entry and self.item_code:
			filters = {
				"parent": self.reference_of_manufacturing_entry,
				"item_code": self.item_code
			}
			if self.batch:
				filters["batch_no"] = self.batch

			# Find matching Stock Entry Detail rows
			stock_details = frappe.get_all(
				"Stock Entry Detail",
				filters=filters,
				fields=["name", "custom_barcodes_v1"]
			)

			for detail in stock_details:
				if not detail.custom_barcodes_v1:
					continue

				# Split into list
				barcode_list = detail.custom_barcodes_v1.split("\n")

				# Remove this barcode (trim whitespace just in case)
				cleaned_list = [bc.strip() for bc in barcode_list if bc.strip() and bc.strip() != self.name.strip()]

				# Join back into string
				updated_barcodes = "\n".join(cleaned_list)

				# Update the field
				frappe.db.set_value(
					"Stock Entry Detail",
					detail.name,
					"custom_barcodes_v1",
					updated_barcodes,
					update_modified=False  # prevents updating modified timestamp unnecessarily
				)
