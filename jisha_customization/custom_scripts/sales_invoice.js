frappe.ui.form.on('Sales Invoice', {
    custom_scan_barcodes: async function (frm) {
        if (!frm.doc.custom_scan_barcodes) return;

        frappe.call({
            method: 'jisha_customization.jisha_customization.override.sales_invoice.get_barcode_data',
            args: { barcode_data: frm.doc.custom_scan_barcodes },
            callback: async function (response) {

                frm.set_value("custom_scan_barcodes", "");

                if (!response || !response.message) return;

                const barcode_data = response.message;

                // ERROR CASE
                if (barcode_data.status === 'error') {
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: barcode_data.message
                    });
                    return;
                }

                const child_data = barcode_data.table_mrql || [];

                // -------------------------------------------------------
                // PRE-FETCH JISHA SETTINGS + SUBGROUPS (used everywhere)
                // -------------------------------------------------------
                const jisha_setting = await frappe.db.get_doc("Jisha Settings");
                const jisha_group = jisha_setting.item_group;
                const jisha_qty = jisha_setting.qty || 1;

                const subgroup_res = await frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                        doctype: "Item Group",
                        filters: { parent_item_group: jisha_group },
                        fields: ["name"]
                    }
                });
                const jisha_subgroups = subgroup_res.message.map(g => g.name);

                // ========================================================
                // ===============  BOX BARCODE PROCESSING  ===============
                // ========================================================
                if (child_data.length > 0) {

                    const first_row = child_data[0];

                    // ALL BARCODE REF LIST
                    const barcodes = child_data.map(r => r.barcode_reference).join("\n");

                    // CHECK EXISTING ROW
                    let existingRow = frm.doc.items.find(
                        item => item.item_code === first_row.item_code &&
                            item.batch_no === first_row.batch
                    );

                    const item_group_res = await frappe.db.get_value("Item", first_row.item_code, "item_group");
                    const item_group = item_group_res.message.item_group;

                    const valid_group =
                        item_group === jisha_group ||
                        jisha_subgroups.includes(item_group);

                    // =============== DUPLICATE BOX CHECK ===============
                    if (existingRow) {

                        const existingBoxes = existingRow.custom_box_creation_reference
                            ? existingRow.custom_box_creation_reference.split("\n")
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
                            return;
                        }

                        // -------------------------------------------------------
                        // UPDATE QTY
                        // -------------------------------------------------------
                        let add_qty = valid_group
                            ? barcode_data.box_qty / jisha_qty
                            : barcode_data.box_qty;

                        existingRow.qty += add_qty;

                        // MERGE BARCODES
                        let existingBarcodes = existingRow.custom_barcodes
                            ? existingRow.custom_barcodes.split("\n")
                            : [];

                        child_data.forEach(r => {
                            if (!existingBarcodes.includes(r.barcode_reference)) {
                                existingBarcodes.push(r.barcode_reference);
                            }
                        });

                        existingRow.custom_barcodes = existingBarcodes.join("\n");

                        // MERGE BOX REFERENCES
                        let existingRefs = existingRow.custom_box_creation_reference
                            ? existingRow.custom_box_creation_reference.split("\n").map(r => r.trim()).filter(Boolean)
                            : [];

                        if (!existingRefs.includes(barcode_data.name)) {
                            existingRefs.push(barcode_data.name);
                        }

                        existingRow.custom_box_creation_reference = existingRefs.join("\n");

                        frm.refresh_field("items");
                        frm.save();
                        return;
                    }

                    // ========================================================
                    // ===============  NEW ROW CREATION  ====================
                    // ========================================================
                    let row =
                        frm.doc.items.find(i => !i.item_code || !i.qty) ||
                        frappe.model.add_child(frm.doc, "Sales Invoice Item", "items");

                    row.item_code = first_row.item_code;
                    row.warehouse = first_row.warehouse;
                    row.batch_no = first_row.batch;
                    row.custom_barcodes = barcodes;
                    row.custom_box_creation_reference = barcode_data.name;
                    row.use_serial_batch_fields = 1;

                    row.qty = valid_group
                        ? barcode_data.box_qty / jisha_qty
                        : barcode_data.box_qty;

                    cur_frm.script_manager.trigger("item_code", row.doctype, row.name);

                    frm.refresh_field("items");
                    frm.save();
                    return;
                }

                // ========================================================
                // ===============  SINGLE BARCODE PROCESSING  ===========
                // ========================================================
                const barcodeName = barcode_data.name;

                // CHECK DUPLICATE BARCODE IN ANY ROW
                const duplicateIndex = frm.doc.items.findIndex(item => {
                    const list = item.custom_barcodes ? item.custom_barcodes.split("\n") : [];
                    return list.includes(barcodeName);
                });

                if (duplicateIndex !== -1) {
                    const dup = frm.doc.items[duplicateIndex];
                    frappe.msgprint({
                        title: __("Duplicate Barcode"),
                        indicator: "red",
                        message: __(
                            `Barcode <b>${barcodeName}</b> is already scanned in row <b>${dup.idx}</b> 
                            (Item: <b>${dup.item_code}</b>, Batch: <b>${dup.batch_no}</b>).`
                        )
                    });
                    return;
                }

                // FIND EXISTING ROW
                let row = frm.doc.items.find(
                    r => r.item_code === barcode_data.item_code &&
                        r.batch_no === barcode_data.batch
                );

                // UPDATE EXISTING ROW
                if (row) {
                    row.qty += 1;
                    row.custom_barcodes = (row.custom_barcodes || "") + `\n${barcodeName}`;
                    frm.refresh_field("items");
                    frm.save();
                    return;
                }

                // CREATE NEW ROW
                row =
                    frm.doc.items.find(i => !i.item_code || !i.qty) ||
                    frappe.model.add_child(frm.doc, "Sales Invoice Item", "items");

                row.item_code = barcode_data.item_code;
                row.warehouse = barcode_data.warehouse;
                row.batch_no = barcode_data.batch;
                row.qty = barcode_data.qty;
                row.custom_barcodes = barcodeName;
                row.use_serial_batch_fields = 1;

                cur_frm.script_manager.trigger("item_code", row.doctype, row.name);

                frm.refresh_field("items");
                frm.save();
            }
        });
    }

});