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
                    frappe.db.set_value("Barcode Entry", barcode, "returned_sales_reference", self.name)
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Returned")
                else:
                    frappe.db.set_value("Barcode Entry", barcode, "reference_of_sales_invoice", self.name)
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Delivered")
        
        for item in self.items:
            if item.custom_box_creation_reference:
                if self.is_return:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "returned_sales_reference", self.name)
                else:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "reference_of_sales_invoice", self.name)

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
                    frappe.db.set_value("Barcode Entry", barcode, "returned_sales_reference", "")
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Delivered")
                else:
                    frappe.db.set_value("Barcode Entry", barcode, "reference_of_sales_invoice", "")
                    frappe.db.set_value("Barcode Entry", barcode, "status", "Active")
        
        for item in self.items:
            if item.custom_box_creation_reference:
                if self.is_return:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "returned_sales_reference", "")
                else:
                    frappe.db.set_value("Box Creation", item.custom_box_creation_reference, "reference_of_sales_invoice", "")

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