// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warehouse Correction", {
	refresh(frm) {
		frm.set_intro("");

		if (frm.doc.is_applied) {
			frm.disable_form();
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

									let handled = false;
									let poll_interval = null;
									let poll_count = 0;
									const max_polls = 10;

									const handle_done = (status, summary) => {
										if (handled) return;
										handled = true;

										clearInterval(poll_interval);
										frappe.realtime.off("warehouse_correction_done", rt_handler);

										frappe.msgprint({
											title: __("Warehouse Correction Complete"),
											message: summary,
											indicator: status === "Success" ? "green" : "red",
										});
										frm.reload_doc();
									};

									const rt_handler = (data) => {
										if (data.docname !== frm.doc.name) return;
										handle_done(data.status, data.message);
									};

									frappe.realtime.on("warehouse_correction_done", rt_handler);

									poll_interval = setInterval(() => {
										poll_count++;

										if (poll_count > max_polls) {
											clearInterval(poll_interval);
											frappe.realtime.off("warehouse_correction_done", rt_handler);
											frappe.show_alert({
												message: __("Warehouse Correction is taking longer than expected. Please refresh to check status."),
												indicator: "orange",
											}, 15);
											return;
										}

										frappe.db.get_value(
											"Warehouse Correction",
											frm.doc.name,
											["is_applied", "status", "correction_summary"]
										).then(r => {
											if (r.message?.is_applied) {
												handle_done(r.message.status, r.message.correction_summary);
											}
										});
									}, 1000);
								}
							}
						});
					}
				);

			}).addClass("btn-primary");
		}
	}
});
