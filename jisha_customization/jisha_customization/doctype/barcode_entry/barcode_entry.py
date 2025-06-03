# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BarcodeEntry(Document):
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
				fields=["name", "custom_barcodes"]
			)

			for detail in stock_details:
				if not detail.custom_barcodes:
					continue

				# Remove this barcode name from the custom_barcodes field
				barcode_list = detail.custom_barcodes.split("\n")
				if self.name in barcode_list:
					barcode_list.remove(self.name)
					updated_barcodes = "\n".join(barcode_list)

					# Update the custom_barcodes field
					frappe.db.set_value(
						"Stock Entry Detail",
						detail.name,
						"custom_barcodes",
						updated_barcodes
					)
			
			frappe.db.commit()
