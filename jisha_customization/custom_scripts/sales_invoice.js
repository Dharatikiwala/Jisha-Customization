frappe.ui.form.on('Sales Invoice', {
    custom_scan_barcodes:function(frm){
        if(frm.doc.custom_scan_barcodes){
            frappe.call({
                method: 'jisha_customization.jisha_customization.override.sales_invoice.get_barcode_data',
                args: {
                    "barcode_data": frm.doc.custom_scan_barcodes
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
                            frm.set_value("custom_scan_barcodes", "");
                            return;
                        }
                        var child_data = barcode_data.table_mrql
                        console.log(barcode_data)
                        
                        if (barcode_data && child_data && child_data.length > 0 ){
                            var barcodes = barcode_data.table_mrql.map(function(row) {
                                return row.barcode_reference;
                            }).join("\n");
                            console.log(barcodes);
                            var barcodeExists = frm.doc.items.some(function(item) {
                                return item.custom_barcodes === barcodes;
                            });

                            if (barcodeExists) {
                                frappe.msgprint('The scanned box barcode already exists in the items table.');
                                frm.set_value("custom_scan_barcodes", "");
                                return
                            } else {
                                frm.doc.items = [];
                                let row;
                                const emptyRow = frm.doc.items.find(item => 
                                    (item.qty === 0 || !item.qty) || 
                                    !item.item_code
                                );
                                
                                if (emptyRow) {
                                    // Use the empty row instead of creating a new one
                                    row = emptyRow;
                                } else {
                                    // If no empty row exists, add a new row
                                    row = frappe.model.add_child(frm.doc, "Sales Invoice Item", "items");
                                }
                                // var row = frappe.model.add_child(frm.doc, "Sales Invoice Item", "items");
                                row.item_code = barcode_data.table_mrql[0].item_code;
                                row.warehouse = barcode_data.table_mrql[0].warehouse;
                                row.batch_no = barcode_data.table_mrql[0].batch;
                                row.qty = barcode_data.box_qty;
                                row.custom_box_creation_reference = barcode_data.name
                                row.custom_barcodes = barcodes;
                                row.use_serial_batch_fields = 1;
                                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                                frm.refresh_field("items");
                                frm.set_value("custom_scan_barcodes", "");
                                frm.save();
                            }
                            
                        }else{

                            var barcodeExistsIndex = frm.doc.items.findIndex(function(item) {
                                var barcodesArray = item.custom_barcodes ? item.custom_barcodes.split("\n") : [];
                                return barcodesArray.includes(barcode_data.name);
                            });
                            if (barcodeExistsIndex !== -1) {
                                frappe.msgprint(`The scanned barcode already exists in the items table at row ${barcodeExistsIndex + 1}.`);
                                frm.set_value("custom_scan_barcodes", "");
                                return;
                            }


                            var existingRow = frm.doc.items.find(function(item) {
                                return item.item_code === barcode_data.item_code && item.batch_no === barcode_data.batch;
                            });

                            if (existingRow) {
                                existingRow.qty += 1;
                                existingRow.custom_barcodes += `\n${barcode_data.name}`;
                                frm.refresh_field("items");
                            } else {
                                let row;
                                const emptyRow = frm.doc.items.find(item => 
                                    (item.qty === 0 || !item.qty) || 
                                    !item.item_code
                                );
                                
                                if (emptyRow) {
                                    // Use the empty row instead of creating a new one
                                    row = emptyRow;
                                } else {
                                    // If no empty row exists, add a new row
                                    row = frappe.model.add_child(frm.doc, "Sales Invoice Item", "items");
                                }

                                // var row = frappe.model.add_child(frm.doc, "Sales Invoice Item", "items");
                                row.item_code = barcode_data.item_code;
                                row.warehouse = barcode_data.warehouse;
                                row.batch_no = barcode_data.batch;
                                row.qty = barcode_data.qty;
                                row.custom_barcodes = barcode_data.name;
                                row.use_serial_batch_fields = 1;
                                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                                frm.refresh_field("items");
                            }

                            frm.set_value("custom_scan_barcodes", "");
                            frm.save();
                        }
                        
                    }
                }
            });
        }
    }
});