// -------------------------
// ✅ Fetch Branch Allocation per Account
// -------------------------
async function get_branch_allocation_details() {
  const res = await frappe.call({
    method: "frappe.client.get",
    args: {
      doctype: "Branch Allocation Rule",
      name: "Branch Allocation Rule",
    },
  });

  const doc = res?.message;
  if (!doc) throw new Error("Cannot read Branch Allocation Rule.");

  const rows = (doc.branch_wise_allocation || [])
    .map(x => ({
      branch: x.branch,
      percentage: parseFloat(x.percentage || 0),
      account: x.chart_of_account,
    }))
    .filter(x => x.branch && x.percentage > 0 && x.account);

  const grouped = {};
  for (const row of rows) {
    if (!grouped[row.account]) grouped[row.account] = [];
    grouped[row.account].push(row);
  }

  for (const [acct, arr] of Object.entries(grouped)) {
    const total = arr.reduce((a, x) => a + x.percentage, 0);
    if (Math.abs(total - 100) > 0.01) {
      throw new Error(`Allocation for ${acct} must total 100%. Current total: ${total}`);
    }
  }

  return grouped;
}

// -------------------------
// ✅ Single Account Root Type Fetch
// -------------------------
async function get_account_root_type(account_name) {
  if (!account_name) return null;
  const res = await frappe.db.get_value("Account", account_name, "root_type");
  return res?.message?.root_type || null;
}

// -------------------------
// ✅ Check if allocation already applied
// -------------------------
function is_already_allocated(rows) {
  if (!rows || !rows.length) return false;
  return rows.every(r => r.custom_is_splitted);
}

// -------------------------
// ✅ Core Function: Apply Branch Allocation
// -------------------------
async function apply_branch_allocation(frm, { force = false } = {}) {
  const rows = frm.doc.accounts || [];

  if (!rows.length) {
    frappe.show_alert({ message: __("⚠️ No account entries to allocate."), indicator: "orange" }, 5);
    return;
  }

  if (!force && is_already_allocated(rows)) {
    frappe.show_alert({
      message: __("ℹ️ Branch allocation already applied. Use 'Force Re-apply' to override."),
      indicator: "blue",
    }, 5);
    return;
  }

  frappe.show_alert({ message: __("⏳ Applying branch allocation..."), indicator: "orange" }, 3);

  try {
    const allocation_map = await get_branch_allocation_details();
    const newRows = [];
    let split_count = 0;

    for (const row of rows) {
      if (!force && row.custom_is_splitted) {
        newRows.push(row);
        continue;
      }

      const root_type = await get_account_root_type(row.account);
      const debit = row.debit_in_account_currency || 0;
      const credit = row.credit_in_account_currency || 0;
      const net = debit - credit;

      if (root_type === "Expense" && net !== 0) {
        const alloc_rows = allocation_map[row.account];
        if (alloc_rows && alloc_rows.length > 0) {
          alloc_rows.forEach(a => {
            const part = net * (a.percentage / 100.0);
            const newRow = { ...row };
            newRow.name = undefined;
            newRow.branch = a.branch;
            newRow.custom_is_splitted = 1;

            if (part >= 0) {
              newRow.debit_in_account_currency = part;
              newRow.credit_in_account_currency = 0;
            } else {
              newRow.debit_in_account_currency = 0;
              newRow.credit_in_account_currency = Math.abs(part);
            }

            newRows.push(newRow);
          });
          split_count++;
        } else {
          row.custom_is_splitted = 1;
          newRows.push(row);
        }
      } else {
        newRows.push(row);
      }
    }

    frm.clear_table("accounts");
    newRows.forEach(nr => frm.add_child("accounts", nr));
    frm.refresh_field("accounts");

    if (split_count > 0) {
      frappe.show_alert({
        message: __(`✅ Branch allocation applied to ${split_count} expense account(s).`),
        indicator: "green",
      }, 5);
    } else {
      frappe.show_alert({
        message: __("ℹ️ No expense accounts found to allocate."),
        indicator: "blue",
      }, 5);
    }
  } catch (e) {
    frappe.msgprint({ title: __("Allocation Error"), message: e.message, indicator: "red" });
  }
}

// -------------------------
// ✅ Journal Entry Hooks
// -------------------------
frappe.ui.form.on("Journal Entry", {
  refresh(frm) {
    frm.add_custom_button(__("Apply Branch Allocation"), async function() {
      try {
        await apply_branch_allocation(frm, { force: false });
      } catch (error) {
        console.error("Branch allocation error:", error);
      }
    });
  },
});
