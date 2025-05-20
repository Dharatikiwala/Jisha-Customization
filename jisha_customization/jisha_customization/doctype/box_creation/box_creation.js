// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Box Creation", {
	refresh(frm) {
        // your code here
	},
    fetch_barcodes:function(frm){

        let args = {};

        if (frm.doc.reference_of_batch && frm.doc.barcode_selection === "Based On Batch") {
            args.batch_no = frm.doc.reference_of_batch;
            args.qty = frm.doc.box_qty
        }

        if (frm.doc.reference_of_stock_entry && frm.doc.barcode_selection === "Based On Stock Entry") {
            args.stock_entry = frm.doc.reference_of_stock_entry;
            args.qty = frm.doc.box_qty
        }

        frappe.call({
            method: "jisha_customization.jisha_customization.doctype.box_creation.box_creation.get_barcode_entry",
            args: args,
            callback: function (r) {
                console.log(r.message);
                if(r.message){
                    frappe.model.clear_table(frm.doc, "table_mrql");
                    for (let item of r.message) {
                        let newrow = frappe.model.add_child(frm.doc, "table_mrql");
                        newrow.barcode_reference = item.name;
                        newrow.item_code = item.item_code;
                        newrow.batch = item.batch;
                        newrow.manufacturing_date = item.manufacturing_date;
                        newrow.warehouse = item.warehouse
                    }
                    frm.refresh_field("table_mrql")
                    setTimeout(() => {
                        frm.save();
                    }, 1000);
                }
            }
        });
    },

    scan_barcode_here:function(frm){
        if(frm.doc.scan_barcode_here){

            if(frm.doc.table_mrql.length >= frm.doc.box_qty ){
                frappe.msgprint(`The box capacity of ${frm.doc.box_qty} has been reached.`)
                return;
            }
            var isDuplicate = frm.doc.table_mrql.some(function(item) {
                return item.barcode_reference === frm.doc.scan_barcode_here;
            });
            if (isDuplicate) {
                var existingRow = frm.doc.table_mrql.find(function(item) {
                    return item.barcode_reference === frm.doc.scan_barcode_here;
                });
                frappe.msgprint(`Barcode Entry already exists in the items table at row ${existingRow.idx}.`);
                frm.set_value("scan_barcode_here", "");
                return;
            }
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Barcode Entry',
                    name: frm.doc.scan_barcode_here
                },
                callback: function (response) {
                    if (response && response.message) {
                        var barcode_data = response.message;
                        console.log(barcode_data)
                        if(frm.doc.table_mrql.length > 0){
                            const item_reference = frm.doc.table_mrql[0].item_code;
                            if (item_reference !== barcode_data.item_code) {
                                frappe.msgprint(`You can only choose one item in the box. The item reference is <b>${item_reference}</b>.`);
                                frm.set_value("scan_barcode_here", "");
                                return;
                            }
                        }
                        
                        let row = frappe.model.add_child(frm.doc, "table_mrql");
                        row.barcode_reference = barcode_data.name;
                        row.item_code = barcode_data.item_code;
                        row.batch = barcode_data.batch;
                        row.manufacturing_date = barcode_data.manufacturing_date;
                        row.warehouse = barcode_data.warehouse
                        
                        frm.refresh_field("table_mrql")
                        frm.set_value("scan_barcode_here", "");
                        frm.save()
                             
                    } else {
                        frm.set_value("scan_barcode_here", "");
                        frappe.msgprint('Barcode Entry not found.');
                    }
                }
            });
        }
    }
});
