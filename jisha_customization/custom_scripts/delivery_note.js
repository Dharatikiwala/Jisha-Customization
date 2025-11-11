frappe.ui.form.on('Delivery Note', {
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
                        // Box barcode processing
                        if (barcode_data && child_data && child_data.length > 0) {
                            var barcodes = barcode_data.table_mrql.map(function (row) {
                                return row.barcode_reference;
                            }).join("\n");

                            var barcodeExists = frm.doc.items.some(function (item) {
                                return item.custom_barcodes === barcodes;
                            });

                            if (barcodeExists) {
                                frappe.msgprint('The scanned barcode already exists in the items table.');
                                frm.set_value("custom_scan_barcodes", "");
                                return;
                            } else {
                                let row;
                                const emptyRow = frm.doc.items.find(item =>
                                    (item.qty === 0 || !item.qty) ||
                                    !item.item_code
                                );

                                if (emptyRow) {
                                    row = emptyRow;
                                } else {
                                    row = frappe.model.add_child(frm.doc, "Delivery Note Item", "items");
                                }

                                const first_item_code = barcode_data.table_mrql[0].item_code;

                                // Step 1: Get the Item Group of scanned item
                                frappe.db.get_value("Item", first_item_code, "item_group")
                                    .then(item_res => {
                                        const item_group = item_res.message.item_group;

                                        // Step 2: Get Jisha Setting
                                        frappe.db.get_doc("Jisha Settings").then(jisha_setting => {
                                            const jisha_group = jisha_setting.item_group;
                                            const jisha_qty = jisha_setting.qty || 1;

                                            // Step 3: Get sub item groups under Jisha group
                                            frappe.call({
                                                method: "frappe.client.get_list",
                                                args: {
                                                    doctype: "Item Group",
                                                    filters: { parent_item_group: jisha_group },
                                                    fields: ["name"]
                                                },
                                                callback: (r) => {
                                                    const sub_groups = r.message.map(g => g.name);
                                                    const valid_group = (item_group === jisha_group) || sub_groups.includes(item_group);

                                                    // Step 4: Assign row values
                                                    row.item_code = first_item_code;
                                                    row.warehouse = barcode_data.table_mrql[0].warehouse;
                                                    row.batch_no = barcode_data.table_mrql[0].batch;
                                                    row.custom_box_creation_reference = barcode_data.name;
                                                    row.custom_barcodes = barcodes;
                                                    row.use_serial_batch_fields = 1;

                                                    // Step 5: Calculate quantity based on Jisha Setting
                                                    if (valid_group) {
                                                        row.qty = barcode_data.box_qty / jisha_qty;
                                                    } else {
                                                        row.qty = barcode_data.box_qty;
                                                    }

                                                    cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                                                    frm.refresh_field("items");
                                                    frm.set_value("custom_scan_barcodes", "");
                                                    frm.save();
                                                }
                                            });
                                        });
                                    });
                                }
                            }
                            // New logic to handle single barcode at a time
                            else{

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
                                        row = frappe.model.add_child(frm.doc, "Delivery Note Item", "items");
                                    }

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