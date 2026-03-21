// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.listview_settings["Warehouse Correction"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const color_map = { Draft: "blue", Success: "green", Error: "red" };
		const status = doc.status || "Draft";
		return [__(status), color_map[status] || "grey", `status,=,${status}`];
	},
	onload(listview) {
		// Block delete triggered via list view bulk actions
		listview.delete_document = function (...args) {
			frappe.throw(__("Warehouse Correction records cannot be deleted."));
		};
	},
};
