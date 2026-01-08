// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Return Barcode Voucher", {
	refresh(frm) {
        frm.set_query('address', () => {
			return {
				filters: {
					'link_doctype':'Customer',
					'link_name': frm.doc.customer
				}
			}
		})
        frm.set_query('company_address', () => {
			return {
				filters: {
					'link_doctype':'Company',
					'link_name': frm.doc.company
				}
			}
		})
            
        frm.add_custom_button("Process Return",function(){
            frappe.call({
                method: 'jisha_customization.jisha_customization.doctype.return_barcode_voucher.return_barcode_voucher.make_voucher_return',
                args:{
                    items:frm.doc.returned_items
                },
                callback:function(r){
                    console.log(r.message)
                    frm.reload_doc()
                }
            })
        })
	},
    address:function(frm){
		if(frm.doc.address){
			return frm.call({
			method: "frappe.contacts.doctype.address.address.get_address_display",
			args: {
			   "address_dict": frm.doc.address
			},
			callback: function(r) {
			  if(r.message)
				  frm.set_value("customer_address", r.message);
				}
		   });
		  }
		  else{
			  frm.set_value("customer_address", "");
		  }
	},
    company_address:function(frm){
		if(frm.doc.company_address){
			return frm.call({
			method: "frappe.contacts.doctype.address.address.get_address_display",
			args: {
			   "address_dict": frm.doc.company_address
			},
			callback: function(r) {
			  if(r.message)
				  frm.set_value("company_address_display", r.message);
				}
		   });
		  }
		  else{
			  frm.set_value("company_address_display", "");
		  }
	},
    scan_barcode:function(frm){
        if(frm.doc.scan_barcode){
            frappe.call({
                method: 'jisha_customization.jisha_customization.doctype.return_barcode_voucher.return_barcode_voucher.get_barcode_data',
                args: {
                    "barcode_data": frm.doc.scan_barcode
                },
                callback: function (response) {
                    if (response && response.message) {
                        var barcode_data = response.message;
                        if (barcode_data.status === 'error') {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: barcode_data.message
                            });
                            frm.set_value("scan_barcode", "");
                            return;
                        }
                        var child_data = barcode_data.table_mrql
                        console.log(barcode_data)
                        
                        if (barcode_data && child_data && child_data.length > 0 ){
                            var barcodes = barcode_data.table_mrql.map(function(row) {
                                return row.barcode_reference;
                            }).join("\n");
                            console.log(barcodes);
                            var barcodeExists = frm.doc.returned_items.some(function(item) {
                                return item.barcodes === barcodes;
                            });

                            if (barcodeExists) {
                                frappe.msgprint('The scanned barcode already exists in the items table.');
                                frm.set_value("scan_barcode", "");
                                return
                            } else {
                                frm.doc.items = [];
                                var row = frappe.model.add_child(frm.doc, "Returned Barcode Table", "returned_items");
                                row.item_code = barcode_data.table_mrql[0].item_code;
                                row.batch_no = barcode_data.table_mrql[0].batch;
                                row.quantity = barcode_data.box_qty;
                                row.box_creation_reference = barcode_data.name
                                row.barcodes = barcodes;
                                row.delivery_note_reference = barcode_data.reference_of_delivery_note ? barcode_data.reference_of_delivery_note : ""
                                row.sales_invoice_reference = barcode_data.reference_of_sales_invoice ? barcode_data.reference_of_sales_invoice : ""
                                frm.refresh_field("returned_items");
                                frm.set_value("scan_barcode", "");
                                frm.save();
                            }
                            
                        }else{

                            var barcodeExistsIndex = frm.doc.returned_items.findIndex(function(item) {
                                var barcodesArray = item.barcodes ? item.barcodes.split("\n") : [];
                                return barcodesArray.includes(barcode_data.name);
                            });
                            if (barcodeExistsIndex !== -1) {
                                frappe.msgprint(`The scanned barcode already exists in the items table at row ${barcodeExistsIndex + 1}.`);
                                frm.set_value("scan_barcode", "");
                                return;
                            }


                            // var existingRow = frm.doc.returned_items.find(function(item) {
                            //     return item.item_code === barcode_data.item_code && item.batch_no === barcode_data.batch;
                            // });
                            var existingRow = frm.doc.returned_items.find(function(item) {
                                return (
                                    item.item_code === barcode_data.item_code &&
                                    item.batch_no === barcode_data.batch &&
                                    item.delivery_note_reference === (barcode_data.reference_of_delivery_note ? barcode_data.reference_of_delivery_note : "") &&
                                    item.sales_invoice_reference === (barcode_data.reference_of_sales_invoice ? barcode_data.reference_of_sales_invoice : "")
                                );
                            });

                            if (existingRow) {
                                existingRow.quantity += 1;
                                existingRow.barcodes += `\n${barcode_data.name}`;
                                frm.refresh_field("returned_items");
                            } else {
                                var row = frappe.model.add_child(frm.doc, "Returned Barcode Table", "returned_items");
                                row.item_code = barcode_data.item_code;
                                row.batch_no = barcode_data.batch;
                                row.quantity = barcode_data.item_qty;
                                row.barcodes = barcode_data.name;
                                // row.box_creation_reference = barcode_data.reference_of_box
                                row.delivery_note_reference = barcode_data.reference_of_delivery_note ? barcode_data.reference_of_delivery_note : "";
                                row.sales_invoice_reference = barcode_data.reference_of_sales_invoice ? barcode_data.reference_of_sales_invoice : "";
                                frm.refresh_field("returned_items");
                            }

                            frm.set_value("scan_barcode", "");
                            frm.save();
                        }
                        
                    } 
                }
            });
        }
    }
});
