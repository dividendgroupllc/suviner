# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Har bir sotib olingan tovarning tan narxi qanday shakllanganini ko'rsatadi:
асосий харид қиймати + унга тақсимланган Доп. расход (Landed Cost) улушлари
= якуний тан нарх (valuation_rate).

Muhim: `landed_cost_voucher_amount` va `valuation_rate` — ERPNextning o'zi
Landed Cost Voucher submit bo'lganda `tabPurchase Invoice Item`ga qaytarib
yozadigan, AVTORITATIV qiymatlar (bu yerda qayta hisoblanmaydi). Faqat
"qaysi Доп. расход qatori (ta'minotchi) qanchasini qo'shdi" degan taqsimot
ERPNextning o'z formulasi (landed_cost_voucher.py::set_applicable_charges_on_item)
asosida shu yerda qayta hisoblanadi — chunki bu taqsimot ERPNextda alohida
saqlanmaydi, faqat item darajasidagi yig'indi saqlanadi.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    if not filters:
        return [], []

    columns = get_columns()
    data = get_data(filters)
    summary_html = get_summary_html(data)

    return columns, data, summary_html


def get_columns():
    return [
        {"fieldname": "posting_date", "label": _("Сана"), "fieldtype": "Date", "width": 90},
        {"fieldname": "purchase_invoice", "label": _("Ҳужжат №"), "fieldtype": "Link", "options": "Purchase Invoice", "width": 130},
        {"fieldname": "company", "label": _("Компания"), "fieldtype": "Link", "options": "Company", "width": 110},
        {"fieldname": "supplier", "label": _("Таъминотчи (асосий)"), "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"fieldname": "item_code", "label": _("Товар коди"), "fieldtype": "Link", "options": "Item", "width": 110},
        {"fieldname": "item_name", "label": _("Товар номи"), "fieldtype": "Data", "width": 200},
        {"fieldname": "qty", "label": _("Миқдори"), "fieldtype": "Float", "precision": 2, "width": 90},
        {"fieldname": "stock_uom", "label": _("Ў.б."), "fieldtype": "Data", "width": 60},
        {"fieldname": "base_net_amount", "label": _("Харид қиймати (асос)"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "item_tax_amount", "label": _("Валюация солиғи"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "landed_cost_voucher_amount", "label": _("Доп. расход — жами"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "total_cost_value", "label": _("Якуний таннарх қиймати"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "valuation_rate", "label": _("Тан нарх (1 бирлик)"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "dop_rasxod_supplier", "label": _("Доп. расход таъминотчиси"), "fieldtype": "Link", "options": "Supplier", "width": 170},
        {"fieldname": "dop_rasxod_description", "label": _("Харажат тури"), "fieldtype": "Data", "width": 160},
        {"fieldname": "item_share_of_row", "label": _("Ушбу таъминотчининг улуши"), "fieldtype": "Currency", "width": 160},
        {"fieldname": "dop_rasxod_expense_account", "label": _("Харажат счети"), "fieldtype": "Link", "options": "Account", "width": 180, "hidden": 1},
        {"fieldname": "item_ratio_pct", "label": _("Товар улуши, %"), "fieldtype": "Percent", "width": 100, "hidden": 1},
        {"fieldname": "distribution_basis", "label": _("Тақсимлаш асоси"), "fieldtype": "Data", "width": 110, "hidden": 1},
        {"fieldname": "pi_item_row", "label": _("(ички калит)"), "fieldtype": "Data", "width": 0, "hidden": 1},
        {"fieldname": "is_item_repeat", "label": _("(ички)"), "fieldtype": "Check", "width": 0, "hidden": 1},
    ]


def get_data(filters):
    pi_rows = get_candidate_invoices(filters)
    if not pi_rows:
        return []

    pi_names = [r.name for r in pi_rows]
    items_by_pi = group_by(get_items_for_invoices(pi_names), "purchase_invoice")
    dop_by_pi = group_by(get_dop_rasxod_rows(pi_names), "purchase_invoice")

    report_rows = []
    for pi in pi_rows:
        report_rows.extend(build_rows_for_invoice(pi, items_by_pi.get(pi.name, []), dop_by_pi.get(pi.name, [])))

    # Item/dop_rasxod_supplier filtrlari qasddan faqat shu yerda, barcha
    # taqsimot hisoblari tugagandan KEYIN qo'llaniladi — chunki nisbat
    # hisobi (total_item_cost, yaxlitlash tuzatuvi) PI'ning BARCHA
    # itemlari/Доп. расход qatorlari asosida bo'lishi shart, aks holda
    # filtrlash boshqa qatorlarning taqsimotini buzib qo'yadi.
    if filters.get("item"):
        report_rows = [r for r in report_rows if r["item_code"] == filters["item"]]
    if filters.get("dop_rasxod_supplier"):
        report_rows = [r for r in report_rows if r.get("dop_rasxod_supplier") == filters["dop_rasxod_supplier"]]

    return report_rows


def build_rows_for_invoice(pi, pi_items, dop_rows):
    eligible_items = [it for it in pi_items if it.is_stock_item or it.is_fixed_asset]
    mode = pi.custom_distribute_charges_based_on or "Amount"
    has_dop_rasxod = bool(pi.custom_dop_rasxod) and bool(dop_rows)
    based_on_field = "qty" if mode == "Qty" else "base_amount"

    total_item_cost = 0.0
    if has_dop_rasxod and mode != "Distribute Manually":
        total_item_cost = sum(flt(it.get(based_on_field)) for it in eligible_items)

    rows = []
    for it in pi_items:
        base_row = {
            "posting_date": pi.posting_date,
            "purchase_invoice": pi.name,
            "company": pi.company,
            "supplier": pi.supplier,
            "item_code": it.item_code,
            "item_name": it.item_name,
            "qty": it.qty,
            "stock_uom": it.stock_uom,
            "base_net_amount": flt(it.base_net_amount),
            "item_tax_amount": flt(it.item_tax_amount),
            "landed_cost_voucher_amount": flt(it.landed_cost_voucher_amount),
            "total_cost_value": flt(it.base_net_amount) + flt(it.item_tax_amount) + flt(it.landed_cost_voucher_amount),
            "valuation_rate": flt(it.valuation_rate),
            "pi_item_row": it.pi_item_row,
        }

        is_eligible = bool(it.is_stock_item or it.is_fixed_asset)

        if not has_dop_rasxod or not is_eligible:
            rows.append({
                **base_row,
                "dop_rasxod_supplier": None,
                "dop_rasxod_description": None,
                "dop_rasxod_expense_account": None,
                "item_share_of_row": None,
                "distribution_basis": None,
                "item_ratio_pct": None,
                "is_item_repeat": 0,
            })
            continue

        if mode == "Distribute Manually":
            # ERPNext bunday holda avtomatik taqsimlamaydi (bizning avtomatik
            # LCV oqimimiz manual qiymatlarni oldindan to'ldirmaydi) — shuning
            # uchun ta'minotchi bo'yicha aniq taqsimot bermaymiz, faqat
            # itemning avtoritativ jami qo'shimcha xarajatini ko'rsatamiz.
            descriptions = sorted({d.description for d in dop_rows if d.description})
            rows.append({
                **base_row,
                "dop_rasxod_supplier": None,
                "dop_rasxod_description": "; ".join(descriptions) or None,
                "dop_rasxod_expense_account": None,
                "item_share_of_row": flt(it.landed_cost_voucher_amount),
                "distribution_basis": _("Aralash/noma'lum taqsimot"),
                "item_ratio_pct": None,
                "is_item_repeat": 0,
            })
            continue

        item_ratio = (flt(it.get(based_on_field)) / total_item_cost) if total_item_cost else 0

        # Har bir Доп. расход qatori uchun ulush — ERPNextning aynan o'zi
        # ishlatgan formula bilan (chiziqli, shuning uchun aniq dekompozitsiya):
        #   item_share_of_row = row.base_amount * item_ratio
        # Yaxlitlash farqi oxirgi qatorga qo'shiladi, shunda yig'indi har
        # doim itemning avtoritativ landed_cost_voucher_amount'iga aniq teng.
        shares = [flt(flt(d.base_amount) * item_ratio, 2) for d in dop_rows]
        diff = flt(flt(it.landed_cost_voucher_amount) - sum(shares), 2)
        if shares:
            shares[-1] = flt(shares[-1] + diff, 2)

        for idx, d in enumerate(dop_rows):
            rows.append({
                **base_row,
                "dop_rasxod_supplier": d.supplier,
                "dop_rasxod_description": d.description,
                "dop_rasxod_expense_account": d.expense_account,
                "item_share_of_row": shares[idx],
                "distribution_basis": mode,
                "item_ratio_pct": flt(item_ratio * 100, 2),
                "is_item_repeat": 0 if idx == 0 else 1,
            })

    return rows


def group_by(rows, key):
    result = {}
    for row in rows:
        result.setdefault(row[key], []).append(row)
    return result


def get_candidate_invoices(filters):
    conditions = [
        "pi.docstatus = 1",
        "pi.posting_date between %(from_date)s and %(to_date)s",
    ]
    values = {"from_date": filters.get("from_date"), "to_date": filters.get("to_date")}

    if filters.get("company"):
        conditions.append("pi.company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("supplier"):
        conditions.append("pi.supplier = %(supplier)s")
        values["supplier"] = filters["supplier"]

    if filters.get("only_with_dop_rasxod"):
        conditions.append("pi.custom_dop_rasxod = 1")

    # item/dop_rasxod_supplier — faqat nomzod hujjatlar ro'yxatini
    # torайтириш uchun (tezlik), taqsimot hisobiga ta'sir qilmasligi
    # uchun item/dop-rasxod QATORLARI darajasida FILTRLANMAYDI (get_data
    # oxirida, hisob-kitobdan keyin qo'llaniladi).
    if filters.get("item"):
        conditions.append("""exists (
            select 1 from `tabPurchase Invoice Item` pii2
            where pii2.parent = pi.name and pii2.item_code = %(item)s
        )""")
        values["item"] = filters["item"]

    if filters.get("dop_rasxod_supplier"):
        conditions.append("""exists (
            select 1 from `tabSuviner Dop Rasxod` dr2
            where dr2.parent = pi.name and dr2.supplier = %(dop_rasxod_supplier)s
        )""")
        values["dop_rasxod_supplier"] = filters["dop_rasxod_supplier"]

    query = f"""
        select pi.name, pi.posting_date, pi.company, pi.supplier,
               pi.custom_dop_rasxod, pi.custom_distribute_charges_based_on
        from `tabPurchase Invoice` pi
        where {' and '.join(conditions)}
        order by pi.posting_date, pi.name
    """
    return frappe.db.sql(query, values, as_dict=True)


def get_items_for_invoices(pi_names):
    if not pi_names:
        return []
    return frappe.db.sql("""
        select pii.name as pi_item_row, pii.parent as purchase_invoice, pii.idx,
               pii.item_code, pii.item_name, pii.qty, pii.stock_uom,
               pii.base_amount, pii.base_net_amount, pii.item_tax_amount,
               pii.landed_cost_voucher_amount, pii.valuation_rate,
               coalesce(it.is_stock_item, 1) as is_stock_item,
               coalesce(it.is_fixed_asset, 0) as is_fixed_asset
        from `tabPurchase Invoice Item` pii
        left join `tabItem` it on it.name = pii.item_code
        where pii.parent in %(pi_names)s
        order by pii.parent, pii.idx
    """, {"pi_names": pi_names}, as_dict=True)


def get_dop_rasxod_rows(pi_names):
    if not pi_names:
        return []
    return frappe.db.sql("""
        select dr.parent as purchase_invoice, dr.name as dop_rasxod_row, dr.idx,
               dr.supplier, dr.description, dr.expense_account, dr.base_amount
        from `tabSuviner Dop Rasxod` dr
        where dr.parent in %(pi_names)s
        order by dr.parent, dr.idx
    """, {"pi_names": pi_names}, as_dict=True)


def get_summary_html(data):
    if not data:
        return ""

    # Item darajasidagi qiymatlar har bir Доп. расход qatorida takrorlangani
    # uchun, summani hisoblashda albatta pi_item_row bo'yicha DEDUP qilish
    # SHART — aks holda 2+ ta'minotchili itemlarning bazaviy qiymati bir
    # necha marta qo'shilib, umumiy summa noto'g'ri (oshirilgan) chiqadi.
    unique_items = {}
    for row in data:
        key = row.get("pi_item_row")
        if key and key not in unique_items:
            unique_items[key] = row

    total_base = sum(flt(r.get("base_net_amount")) for r in unique_items.values())
    total_tax = sum(flt(r.get("item_tax_amount")) for r in unique_items.values())
    total_dop_rasxod = sum(flt(r.get("landed_cost_voucher_amount")) for r in unique_items.values())
    total_final = total_base + total_tax + total_dop_rasxod
    dop_rasxod_pct = (total_dop_rasxod / total_final * 100) if total_final else 0

    def fmt(val):
        return f"{flt(val):,.2f}"

    return f"""
    <div style="margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 5px;">
        <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead>
                <tr style="background-color: #f0f0f0;">
                    <th style="padding: 10px; text-align: left; border: 1px solid #ddd; width: 60%;"></th>
                    <th style="padding: 10px; text-align: right; border: 1px solid #ddd; width: 40%;">{_("Сумма")}</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 500;">{_("Умумий харид қиймати")}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{fmt(total_base)}</td>
                </tr>
                <tr style="background-color: #fafafa;">
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 500;">{_("Умумий валюация солиғи")}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{fmt(total_tax)}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 500;">{_("Умумий Доп. расход")}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{fmt(total_dop_rasxod)}</td>
                </tr>
                <tr style="background-color: #fafafa;">
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">{_("Якуний таннарх")}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{fmt(total_final)}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd; font-weight: 500;">{_("Доп. расходнинг улуши")}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: right;">{dop_rasxod_pct:,.1f}%</td>
                </tr>
            </tbody>
        </table>
    </div>
    """
