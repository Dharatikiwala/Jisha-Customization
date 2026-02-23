frappe.ui.form.on('Stock Entry', {
    refresh(frm) {
        if(frm.doc.docstatus === 1 && (frm.doc.purpose === "Manufacture" || frm.doc.purpose === "Material Receipt")) {
            frm.add_custom_button("Generate Barcode Entry", function() {
                frappe.call({
                    method: "jisha_customization.jisha_customization.override.stock_entry.create_barcode_entry",
                    args: {
                        "doc": frm.doc
                    },
                    freeze:true,
                    freeze_message: __("Generating Barcode Entry..."),
                    callback: function(r) {
                        console.log(r.message);
                        frm.reload_doc()
                    }
                });
            });
        }

        // Check if any item in frm.doc.items has custom_barcodes_v1 value
        var hasCustomBarcodes = frm.doc.items.some(item => !!item.custom_barcodes_v1);
        if(frm.doc.docstatus === 1 && hasCustomBarcodes) {
            frm.add_custom_button("Create Box", function() {
                frappe.call({
                    method: "jisha_customization.jisha_customization.override.stock_entry.get_items",
                    args: {
                        "doc_name": frm.doc.name
                    },
                    freeze:true,
                    callback: function(r) {
                        if(r.message){
                            // create dialog box where we can add data of r.meesage in child table
                            var fields = [
                                
                                {
                                    fieldtype: "Table",
                                    fieldname: "items_table",
                                    label: "Items",
                                    fields: [
                                        {
                                            fieldtype: "Data",
                                            fieldname: "item_code",
                                            label: "Item Code",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 2
                                        },
                                        {
                                            fieldtype: "Link",
                                            fieldname: "batch_no",
                                            label: "Batch",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Float",
                                            fieldname: "qty",
                                            label: "Qty",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Int",
                                            fieldname: "barcode_qty",
                                            label: "Barcode Qty",
                                            read_only: 1,
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Int",
                                            fieldname: "divide",
                                            label: "Divide",
                                            in_list_view: 1,
                                            columns: 1,
                                            onchange: function () {
                                                const divide = this.get_value();
                                                console.log(divide);
                                                const barcode_qty = this.grid_row.on_grid_fields_dict.barcode_qty.get_value();
                                                if(divide <= 0){
                                                    frappe.msgprint("Divide value must be greater than 0.");
                                                    return;
                                                }

                                                if (divide && barcode_qty) {
                                                    const full_box_val = barcode_qty / divide;
                                                    // Integer part
                                                    const full_box = Math.floor(full_box_val);
                                                    // Fractional part
                                                    const remaining_box = +(full_box_val - full_box).toFixed(5);

                                                    this.grid_row.on_grid_fields_dict.full_box.set_value(full_box);
                                                    this.grid_row.on_grid_fields_dict.remaining_box.set_value(remaining_box);
                                                } else {
                                                    this.grid_row.on_grid_fields_dict.full_box.set_value(0);
                                                    this.grid_row.on_grid_fields_dict.remaining_box.set_value(0);
                                                }
                                            }

                                        },
                                        {
                                            fieldtype: "Int",
                                            fieldname: "full_box",
                                            label: "Full Box",
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        {
                                            fieldtype: "Float",
                                            fieldname: "remaining_box",
                                            label: "Remaining Box",
                                            in_list_view: 1,
                                            columns: 1
                                        },
                                        // {
                                        //     fieldtype: "small_text",
                                        //     fieldname: "custom_barcodes_v1",
                                        //     label: "Custom Barcodes",
                                        //     in_list_view: 0
                                        // }
                                    ]
                                }
                            ];

                            var dialog = new frappe.ui.Dialog({
                                title: "Items",
                                fields: fields,
                                 size: 'extra-large',
                                primary_action_label: "Create Box",
                                primary_action(values) {
                                    let selected_items = values.items_table.filter(item => item.divide > 0 && item.full_box > 0);
                                    if (selected_items.length === 0) {
                                        frappe.msgprint({
                                            title: __("No Items Selected"),
                                            message: __("Please select at least one item with 'divide' > 0 and 'full_box' > 0."),
                                            indicator: "red"
                                        });
                                        return;
                                    }
                                    frappe.call({
                                        method: "jisha_customization.jisha_customization.override.stock_entry.create_box_creation",
                                        args: {
                                            "item_dict": JSON.stringify(selected_items),
                                            "stock_entry": frm.doc.name,
                                            "date":frm.doc.posting_date
                                        },
                                        freeze:true,
                                        freeze_message: __("Creating Box..."),
                                        callback: function(r) {
                                            console.log(r.message)
                                            if (r.message && r.message.created_items) {
                                                let msg = r.message.created_items.map(item => {
                                                    return `<b>${item.item_code}</b>: ${item.boxes.join(", ")}`;
                                                }).join("<br>");

                                                frappe.msgprint({
                                                    title: __("Box Creation Summary"),
                                                    message: msg,
                                                    indicator: 'green'
                                                });
                                            }
                                        }
                                    });

                                    dialog.hide()
                                }
                            });

                            // Populate child table with data from r.message
                            if (Array.isArray(r.message)) {
                                let table_field = dialog.fields_dict.items_table;

                                // Ensure the table has data array
                                if (!table_field.df.data) {
                                    table_field.df.data = [];
                                }

                                r.message.forEach(function(item) {
                                    table_field.df.data.push({
                                        item_code: item.item_code,
                                        batch_no:item.batch_no,
                                        qty: item.qty,
                                        warehouse:item.t_warehouse,
                                        barcode_qty: item.barcode_count,
                                        custom_barcodes_v1: item.custom_barcodes_v1 || "",
                                    });
                                });

                                table_field.refresh();
                            }

                            dialog.show();


                        }
                    }
                });
            });
        }
    },

    custom_scan_barcodes: function (frm) {

        const resetScanner = () => frm.set_value("custom_scan_barcodes", "");

        const getJishaDetails = (item_code) => {
            return frappe.db.get_value("Item", item_code, "item_group").then(item_res => {
                return frappe.db.get_doc("Jisha Settings").then(jisha_setting => {
                    return frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Item Group",
                            filters: { parent_item_group: jisha_setting.item_group },
                            fields: ["name"],
                            limit_page_length: 100
                        }
                    }).then(r => {
                        return {
                            item_group: item_res.message.item_group,
                            jisha_group: jisha_setting.item_group,
                            jisha_qty: jisha_setting.qty || 1,
                            sub_groups: r.message.map(g => g.name)
                        };
                    });
                });
            });
        };

        const applyJishaQty = (is_valid_group, box_qty, jisha_qty) =>
            is_valid_group ? (box_qty / jisha_qty) : box_qty;

        const mergeValues = (existing_list, new_values) => {
            let list = existing_list ? existing_list.split("\n") : [];
            new_values.forEach(v => { if (!list.includes(v)) list.push(v); });
            return list.join("\n");
        };

        if (!frm.doc.custom_scan_barcodes) return;

        frappe.call({
            method: 'jisha_customization.jisha_customization.override.sales_invoice.get_barcode_data',
            args: { "barcode_data": frm.doc.custom_scan_barcodes },

            callback: function (response) {

                if (!response || !response.message) return;

                const barcode_data = response.message;

                if (barcode_data.status === 'error') {
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: barcode_data.message
                    });
                    resetScanner();
                    return;
                }

                const child_data = barcode_data.table_mrql;

                // =====================================================================================
                // CASE 1: BOX BARCODE (MULTIPLE ENTRIES)
                // =====================================================================================
                if (child_data && child_data.length > 0) {

                    const first = child_data[0];

                    const barcodes = child_data.map(row => row.barcode_reference).join("\n");

                    // ---------------------------------------------
                    // FIND EXISTING ROW FOR SAME ITEM + BATCH
                    // ---------------------------------------------
                    let existingRow = frm.doc.items.find(item =>
                        item.item_code === first.item_code &&
                        item.batch_no === first.batch && item.s_warehouse === first.warehouse
                    );

                    // =================================================================================
                    // CASE 1A: UPDATE EXISTING ROW
                    // =================================================================================
                    if (existingRow) {

                        let existingBoxes = existingRow.custom_box_reference
                            ? existingRow.custom_box_reference.split("\n")
                            : [];

                        if (existingBoxes.includes(barcode_data.name)) {
                            frappe.msgprint({
                                title: __("Duplicate Box"),
                                indicator: "red",
                                message: __(
                                    `Box <b>${barcode_data.name}</b> is already scanned in row <b>${existingRow.idx}</b> 
                                    (Item: <b>${existingRow.item_code}</b>, Batch: <b>${existingRow.batch_no}</b>).`
                                )
                            });
                            resetScanner();
                            return;
                        }

                        // → JISHA GROUP LOGIC
                        getJishaDetails(first.item_code).then(data => {

                            const valid_group =
                                data.item_group === data.jisha_group ||
                                data.sub_groups.includes(data.item_group);

                            // → UPDATE QTY
                            existingRow.qty += applyJishaQty(
                                valid_group,
                                barcode_data.box_qty,
                                data.jisha_qty
                            );

                            // → MERGE BARCODES
                            existingRow.custom_barcodes_v1 =
                                mergeValues(existingRow.custom_barcodes_v1, child_data.map(x => x.barcode_reference));

                            // → MERGE BOX REF
                            existingRow.custom_box_reference =
                                mergeValues(existingRow.custom_box_reference, [barcode_data.name]);

                            frm.refresh_field("items");
                            resetScanner();
                            frm.save();
                        });

                        return;
                    }

                    // =================================================================================
                    // CASE 1B: CREATE NEW ROW
                    // =================================================================================
                    let row = frm.doc.items.find(i => (!i.qty || !i.item_code)) ||
                        frappe.model.add_child(frm.doc, "Stock Entry Detail", "items");

                    getJishaDetails(first.item_code).then(data => {

                        const valid_group =
                            data.item_group === data.jisha_group ||
                            data.sub_groups.includes(data.item_group);

                        row.item_code = first.item_code;
                        row.s_warehouse = first.warehouse;
                        row.batch_no = first.batch;

                        row.custom_box_reference = barcode_data.name;
                        row.custom_barcodes_v1 = barcodes;
                        row.use_serial_batch_fields = 1;

                        row.qty = applyJishaQty(
                            valid_group,
                            barcode_data.box_qty,
                            data.jisha_qty
                        );

                        cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                        frm.refresh_field("items");
                        resetScanner();
                        frm.save();
                    });

                    return;
                }

                // =====================================================================================
                // CASE 2: SINGLE BARCODE
                // =====================================================================================

                let barcodeExistsIndex = frm.doc.items.findIndex(item => {
                    let arr = item.custom_barcodes_v1 ? item.custom_barcodes_v1.split("\n") : [];
                    return arr.includes(barcode_data.name);
                });

                if (barcodeExistsIndex !== -1) {
                    let r = frm.doc.items[barcodeExistsIndex];
                    frappe.msgprint({
                        title: __("Duplicate Barcode"),
                        indicator: "red",
                        message: __(
                            `Barcode <b>${barcode_data.name}</b> is already scanned in row <b>${r.idx}</b> 
                            (Item: <b>${r.item_code}</b>, Batch: <b>${r.batch_no}</b>).`
                        )
                    });
                    resetScanner();
                    return;
                }

                let existingRow = frm.doc.items.find(item =>
                    item.item_code === barcode_data.item_code &&
                    item.batch_no === barcode_data.batch && item.s_warehouse === barcode_data.warehouse
                );

                if (existingRow) {
                    existingRow.qty += 1;
                    existingRow.custom_barcodes_v1 =
                        mergeValues(existingRow.custom_barcodes_v1, [barcode_data.name]);

                    frm.refresh_field("items");
                    resetScanner();
                    frm.save();
                    return;
                }

                // → NEW ROW FOR SINGLE BARCODE
                let row = frm.doc.items.find(i => (!i.qty || !i.item_code)) ||
                    frappe.model.add_child(frm.doc, "Stock Entry Detail", "items");

                row.item_code = barcode_data.item_code;
                row.s_warehouse = barcode_data.warehouse;
                row.batch_no = barcode_data.batch;
                row.qty = parseFloat(barcode_data.item_qty);
                row.custom_barcodes_v1 = barcode_data.name;
                row.use_serial_batch_fields = 1;

                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);
                frm.refresh_field("items");
                resetScanner();
                frm.save();
            }
        });
    }


});