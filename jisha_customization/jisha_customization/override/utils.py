import frappe

def update_box_references():
    """
    Migrate custom_box_creation_reference to custom_box_creation_reference_long
    for Delivery Note Item and Sales Invoice Item (optimized for large datasets)
    """

    doctypes = ["Delivery Note Item", "Sales Invoice Item"]
    batch_size = 1000  # Process in chunks to avoid memory issues

    for doctype in doctypes:
        try:
            table_name = f"tab{doctype}"

            print(f"\n🚀 Checking {doctype}...")

            # ✅ Get total count first
            total_count = frappe.db.sql(f"""
                SELECT COUNT(*)
                FROM `{table_name}`
                WHERE custom_box_creation_reference IS NOT NULL
                  AND custom_box_creation_reference != ''
                  AND TRIM(custom_box_creation_reference) != ''
            """)[0][0]

            if total_count == 0:
                print(f"ℹ️ No records to migrate for {doctype}")
                continue

            print(f"🔄 Starting migration for {doctype}: {total_count} records")

            offset = 0
            migrated_count = 0

            # ✅ Process in batches
            while offset < total_count:

                records = frappe.db.sql(f"""
                    SELECT name, custom_box_creation_reference
                    FROM `{table_name}`
                    WHERE custom_box_creation_reference IS NOT NULL
                      AND custom_box_creation_reference != ''
                      AND TRIM(custom_box_creation_reference) != ''
                    LIMIT {batch_size} OFFSET {offset}
                """, as_dict=1)

                if not records:
                    break

                for record in records:
                    frappe.db.set_value(
                        doctype,
                        record.name,
                        "custom_box_creation_reference_long",
                        record.custom_box_creation_reference.strip(),
                        update_modified=False
                    )

                migrated_count += len(records)
                offset += batch_size

                frappe.db.commit()

                progress = (migrated_count / total_count) * 100

                print(
                    f"📊 {doctype}: {migrated_count}/{total_count} "
                    f"({progress:.1f}%) migrated"
                )

            print(f"✅ Completed {doctype}: {migrated_count} records migrated")

        except Exception as e:
            frappe.db.rollback()
            print(f"❌ Failed for {doctype}: {str(e)}")
            frappe.log_error(
                frappe.get_traceback(),
                f"Patch Error: Copy custom_box_creation_reference for {doctype}"
            )
            continue
