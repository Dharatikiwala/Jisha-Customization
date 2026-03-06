// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Correction", {
	refresh(frm) {
		frm.set_intro("");

		if (frm.doc.is_applied) {
			frm.disable_form();

			if (frm.doc.correction_status) {
				const color = frm.doc.correction_status === "Success" ? "green" : "red";
				frm.page.set_indicator(__(frm.doc.correction_status), color);
			}
			return;
		}

		if (!frm.is_new()) {
			frm.set_intro(__("Data saved! Click on 'Apply Warehouse Correction' to apply correction."), "yellow");
		}

		if (!frm.doc.items || !frm.doc.items.length) return;

		const has_unprocessed = frm.doc.items.some(d => !d.is_processed);

		if (has_unprocessed) {
			frm.add_custom_button(__("Apply Warehouse Correction"), () => {

				frappe.confirm(
					__(
						"This action will update warehouse values based on row Type.<br><br>" +
						"<b>This operation cannot be undone.</b><br><br>" +
						"Do you want to continue?"
					),
					() => {
						frappe.call({
							method: "jisha_customization.jisha_customization.doctype.warehouse_correction.warehouse_correction.run_warehouse_correction",
							args: { docname: frm.doc.name },
							callback(r) {
								if (!r.exc) {
									frappe.show_alert({
										message: __(r.message.message),
										indicator: "blue",
									}, 10);

									frappe.realtime.on("warehouse_correction_done", function handler(data) {
										if (data.docname !== frm.doc.name) return;
										frappe.realtime.off("warehouse_correction_done", handler);

										frappe.msgprint({
											title: __("Warehouse Correction Complete"),
											message: data.message,
											indicator: data.status === "Success" ? "green" : "red",
										});
										frm.reload_doc();
									});
								}
							}
						});
					}
				);

			}).addClass("btn-primary");
		}
	}
});
