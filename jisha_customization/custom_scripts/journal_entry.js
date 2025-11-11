frappe.ui.form.on("Journal Entry", {
    async validate(frm) {
        try {
            if (!frm.doc.accounts || frm.doc.accounts.length === 0) return;

            // ✅ Skip validation if all child rows are already split
            const unsplit = frm.doc.accounts.filter(r => !r.custom_is_splitted);
            if (unsplit.length === 0) {
                console.log("All accounts already splitted, skipping branch allocation.");
                return;
            }

            const res = await frappe.call({
                method: "jisha_customization.jisha_customization.doctype.jisha_settings.jisha_settings.split_journal_entry_lines",
                args: { doc_json: JSON.stringify(frm.doc) },
            });

            if (res.message) {
                frm.clear_table("accounts");
                (res.message.accounts || []).forEach(r => {
                const row = frm.add_child("accounts");
                Object.keys(r).forEach(k => {
                    if (["doctype", "__islocal", "idx"].includes(k)) return;
                    row[k] = r[k];
                });
                });

                frm.refresh_field("accounts");
                frappe.show_alert({
                message: "✅ Branch Allocation applied successfully!",
                indicator: "green",
                });
            }

        } 
        catch (e) {
            console.error("Branch Allocation Error:", e);
            frappe.msgprint({
                title: "Branch Allocation Error",
                message: e.message || e,
                indicator: "red",
            });
        }
    },
});
