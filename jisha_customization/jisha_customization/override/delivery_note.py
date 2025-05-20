import frappe

def on_submit(self,method):
    if self.items:
        barcodes_to_update = [
            barcode.strip()
            for item in self.items if item.custom_barcodes
            for barcode in item.custom_barcodes.split("\n")
        ]
        if barcodes_to_update:
            for barcode in barcodes_to_update:
                if self.is_return:
                    frappe.db.set_value("Barcode Entry", barcode, "returned_delivery_reference", self.name)
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Returned")
                else:
                    frappe.db.set_value("Barcode Entry", barcode, "reference_of_delivery_note", self.name)
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Delivered")
                frappe.db.commit()
        
        for item in self.items:
            if item.custom_box_creation_reference:
                if self.is_return:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "returned_delivery_reference", self.name)
                else:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "reference_of_delivery_note", self.name)
                frappe.db.commit()

def on_cancel(self,method):
    if self.items:
        barcodes_to_update = [
            barcode.strip()
            for item in self.items if item.custom_barcodes
            for barcode in item.custom_barcodes.split("\n")
        ]
        if barcodes_to_update:
            for barcode in barcodes_to_update:
                if self.is_return:
                    frappe.db.set_value("Barcode Entry", barcode, "returned_delivery_reference", "")
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Delivered")
                else:
                    frappe.db.set_value("Barcode Entry", barcode, "reference_of_delivery_note", "")
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Active")
                frappe.db.commit()
        
        for item in self.items:
            if item.custom_box_creation_reference:
                if self.is_return:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "returned_delivery_reference", "")
                else:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "reference_of_delivery_note", "")
                frappe.db.commit()