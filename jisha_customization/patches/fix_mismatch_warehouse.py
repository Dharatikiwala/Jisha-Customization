import frappe

def execute():
    """
    Patch: Sync Barcode Box.warehouse with Barcode Entry.warehouse
    - Uses a for-loop with fixed iterations to avoid infinite loops.
    """
    batch_size = 1000
    total_updated = 0

    # Count total mismatches upfront for progress tracking
    total_mismatches = frappe.db.sql("""
        SELECT COUNT(*) AS total
        FROM `tabBarcode Entry` be
        INNER JOIN `tabBarcode Box` bb ON be.name = bb.barcode_reference
        WHERE be.reference_of_box IS NOT NULL
          AND IFNULL(be.warehouse, '') != IFNULL(bb.warehouse, '')
    """, as_dict=1)[0]["total"]

    print(f"Total mismatches to fix: {total_mismatches}")

    # Calculate how many batches we need
    total_batches = -(-total_mismatches // batch_size)  # ceiling division

    for batch_no in range(total_batches):
        mismatches = frappe.db.sql("""
            SELECT 
                be.name AS barcode,
                be.warehouse AS barcode_warehouse,
                bc.name AS box_name,
                bb.name AS child_row,
                bb.warehouse AS box_warehouse
            FROM `tabBarcode Entry` be
            INNER JOIN `tabBarcode Box` bb 
                ON be.name = bb.barcode_reference
            INNER JOIN `tabBox Creation` bc 
                ON bc.name = bb.parent
            WHERE be.reference_of_box IS NOT NULL
              AND IFNULL(be.warehouse, '') != IFNULL(bb.warehouse, '')
            LIMIT %(limit)s
        """, {"limit": batch_size}, as_dict=1)

        if not mismatches:
            break

        # Update each child row
        for row in mismatches:
            frappe.db.set_value(
                "Barcode Box",
                {"name": row["child_row"], "parent": row["box_name"]},
                "warehouse",
                row["barcode_warehouse"],
                update_modified=False
            )
            total_updated += 1

        frappe.db.commit()
        print(f"Batch {batch_no + 1}/{total_batches}: Updated {len(mismatches)} rows (Total so far: {total_updated})")

    frappe.log_error(
        title="Patch completed: Barcode→Box warehouse sync",
        message=f"Total mismatched rows updated: {total_updated} / {total_mismatches}"
    )
