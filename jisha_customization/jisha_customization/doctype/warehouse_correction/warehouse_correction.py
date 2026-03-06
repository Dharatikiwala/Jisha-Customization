# Copyright (c) 2026, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WarehouseCorrection(Document):

	def validate(self):
		if self.is_applied:
			frappe.throw(_("This record has been applied and cannot be edited."))


@frappe.whitelist()
def run_warehouse_correction(docname):
	"""Enqueues the warehouse correction and notifies via realtime when done."""
	user = frappe.session.user
	frappe.enqueue(
		"jisha_customization.jisha_customization.doctype.warehouse_correction.warehouse_correction._apply_correction",
		docname=docname,
		user=user,
		queue="long",
		timeout=600,
		now=frappe.flags.in_test,
	)
	return {"message": _("Warehouse correction has been queued. You will be notified once it's done.")}


def _apply_correction(docname, user):
	"""Background job: applies warehouse correction using bulk SQL updates."""
	doc = frappe.get_doc("Warehouse Correction", docname)

	if not doc.items:
		frappe.publish_realtime(
			"warehouse_correction_done",
			{"docname": docname, "status": "Error", "message": _("No Warehouse Correction Items found.")},
			user=user,
		)
		return

	barcode_updated = 0
	box_updated = 0
	error_count = 0
	error_logs = []
	processed_row_names = []

	for item in doc.items:

		if item.is_processed:
			continue

		warehouse = item.warehouse
		row_type = (item.type or "").strip()
		barcodes = _parse_list(item.barcodes)
		box_refs = _parse_list(item.box_references)

		if not warehouse:
			continue

		row_updated = False

		# =====================================================
		# TYPE = BARCODE
		# =====================================================
		if row_type == "Barcode":

			if not barcodes:
				error_logs.append(f"Row {item.idx}: No barcodes provided.")
				error_count += 1
				continue

			existing = set(frappe.db.get_all(
				"Barcode Entry", filters={"name": ["in", barcodes]}, pluck="name"
			))
			missing = set(barcodes) - existing
			for m in missing:
				error_logs.append(f"Barcode Entry not found: {m}")
			error_count += len(missing)

			if existing:
				ph = ", ".join(["%s"] * len(existing))
				frappe.db.sql(
					f"UPDATE `tabBarcode Entry` SET warehouse=%s WHERE name IN ({ph})",
					[warehouse] + list(existing),
				)
				barcode_updated += len(existing)
				row_updated = True

		# =====================================================
		# TYPE = BOX
		# =====================================================
		elif row_type == "Box":

			if not box_refs:
				error_logs.append(f"Row {item.idx}: No Box References provided.")
				error_count += 1
				continue

			existing_boxes = set(frappe.db.get_all(
				"Box Creation", filters={"name": ["in", box_refs]}, pluck="name"
			))
			missing_boxes = set(box_refs) - existing_boxes
			for m in missing_boxes:
				error_logs.append(f"Box Creation not found: {m}")
			error_count += len(missing_boxes)

			if existing_boxes:
				child_rows = frappe.db.get_all(
					"Barcode Box",
					filters={"parent": ["in", list(existing_boxes)], "parenttype": "Box Creation"},
					fields=["name", "barcode_reference"],
				)

				if not child_rows:
					error_logs.append(f"No Barcode rows found in Boxes: {', '.join(existing_boxes)}")
					error_count += 1
				else:
					child_names = [r.name for r in child_rows]
					barcode_refs = [r.barcode_reference for r in child_rows if r.barcode_reference]

					ph = ", ".join(["%s"] * len(child_names))
					frappe.db.sql(
						f"UPDATE `tabBarcode Box` SET warehouse=%s WHERE name IN ({ph})",
						[warehouse] + child_names,
					)

					if barcode_refs:
						ph2 = ", ".join(["%s"] * len(barcode_refs))
						frappe.db.sql(
							f"UPDATE `tabBarcode Entry` SET warehouse=%s WHERE name IN ({ph2})",
							[warehouse] + barcode_refs,
						)

					box_updated += len(child_rows)
					row_updated = True

		else:
			error_logs.append(f"Row {item.idx}: Invalid type '{row_type}'")
			error_count += 1

		if row_updated:
			processed_row_names.append(item.name)

	# Bulk-mark rows as processed
	if processed_row_names:
		ph = ", ".join(["%s"] * len(processed_row_names))
		frappe.db.sql(
			f"UPDATE `tabWarehouse Correction Item` SET is_processed=1 WHERE name IN ({ph})",
			processed_row_names,
		)

	if error_logs:
		frappe.log_error(title="Warehouse Correction Errors", message="\n".join(error_logs))

	correction_status = "Error" if error_count > 0 else "Success"
	corrected_by_name = frappe.db.get_value("User", user, "full_name") or user

	frappe.db.set_value(
		"Warehouse Correction",
		docname,
		{
			"is_applied": 1,
			"corrected_by": user,
			"corrected_by_name": corrected_by_name,
			"corrected_at": frappe.utils.now_datetime(),
			"correction_status": correction_status,
		},
		update_modified=False,
	)

	processed_rows = len(processed_row_names)
	message = (
		f"Warehouse Correction Status.<br><br>"
		f"<b>Rows Processed:</b> {processed_rows}<br>"
		f"<b>Barcodes Updated:</b> {barcode_updated}<br>"
		f"<b>Box Rows Updated:</b> {box_updated}<br>"
		f"<b>Errors:</b> {error_count}"
	)

	frappe.publish_realtime(
		"warehouse_correction_done",
		{"docname": docname, "status": correction_status, "message": message},
		user=user,
	)


def _parse_list(value):
	if not value:
		return []

	return [v.strip() for v in value.replace(",", "\n").split("\n") if v.strip()]
