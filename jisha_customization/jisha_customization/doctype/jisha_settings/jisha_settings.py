# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class JishaSettings(Document):
	pass


@frappe.whitelist()
def get_branch_allocation_details(account_list=None):
	import json
	if isinstance(account_list, str):
		try:
			account_list = json.loads(account_list)
		except Exception:
			account_list = [account_list]

	allocation_doc = frappe.get_single("Branch Allocation Rule")
	if not allocation_doc:
		frappe.throw(_("Branch Allocation Rule not found"))

	if not getattr(allocation_doc, "is_active", 1):
		frappe.throw(_("Branch Allocation Rule is not active"))

	rules = allocation_doc.get("branch_wise_allocation") or []
	result = {}

	def norm(s):
		return (s or "").strip().lower()

	for r in rules:
		account = r.get("chart_of_account") or r.get("account") or r.get("expense_account")
		if not account:
			continue
		if account_list and all(norm(account) != norm(a) for a in account_list):
			continue
		result.setdefault(norm(account), []).append({
			"branch": r.branch,
			"percentage": float(r.percentage or 0)
		})

	for acc, rows in result.items():
		total = sum(r["percentage"] for r in rows)
		if abs(total - 100) > 0.1:
			frappe.throw(f"Total for {acc} must be 100%. Current: {total}%")

	return result


@frappe.whitelist()
def split_journal_entry_lines(doc_json):
	"""Split only those JE lines not already split (checked via child field custom_is_splitted)."""
	import json
	doc = json.loads(doc_json)

	if not doc.get("accounts"):
		return doc

	# Collect all accounts
	accounts = [row.get("account") for row in doc.get("accounts", []) if row.get("account")]
	allocation_map = get_branch_allocation_details(json.dumps(accounts))

	def norm(s):
		return (s or "").strip().lower()

	def find_alloc(account):
		acc_norm = norm(account)
		for key, val in allocation_map.items():
			if acc_norm == key or key in acc_norm or acc_norm in key:
				return val
		return None

	new_rows = []

	for row in doc.get("accounts", []):
		# ✅ Skip already split lines
		if row.get("custom_is_splitted"):
			new_rows.append(row)
			continue

		account = row.get("account")
		root_type = frappe.db.get_value("Account", account, "root_type")
		debit = row.get("debit_in_account_currency") or 0
		credit = row.get("credit_in_account_currency") or 0
		net = debit - credit

		if root_type == "Expense" and abs(net) > 0:
			allocs = find_alloc(account)
			if allocs:
				for a in allocs:
					part = net * (a["percentage"] / 100.0)
					new_row = row.copy()
					new_row["branch"] = a["branch"]
					new_row["custom_is_splitted"] = 1  # ✅ mark split at child level
					if part >= 0:
						new_row["debit_in_account_currency"] = part
						new_row["credit_in_account_currency"] = 0
					else:
						new_row["debit_in_account_currency"] = 0
						new_row["credit_in_account_currency"] = abs(part)
					new_row.pop("name", None)
					new_rows.append(new_row)
			else:
				new_rows.append(row)
		else:
			new_rows.append(row)

	doc["accounts"] = new_rows
	return doc


