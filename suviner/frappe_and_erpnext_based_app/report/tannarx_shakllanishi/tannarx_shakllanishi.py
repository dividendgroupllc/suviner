# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Sebestoimost Tovara — har bir sotib olingan tovar tannarxi QANDAY
shakllanganini ikir-chikirigacha ko'rsatadi (daraxt-ko'rinish):

  📦 Tovar (hujjat, miqdor, kg, YAKUNIY tannarx, 1 dona narxi)
     ↳ Харид нархи (асос)
     ↳ Валюация солиғи (bo'lsa)
     ↳ har bir Доп. расход komponenti: ta'minotchi, usul (Qty/Amount/Kg),
       tovar ulushi %, summa, 1 donaga to'g'ri kelgani

MANBA — taxmin emas, avtoritativ hujjatlar:
- item darajasi: tabPurchase Invoice Item (base_net_amount, item_tax_amount,
  landed_cost_voucher_amount, valuation_rate — ERPNextning o'zi yozadi);
- komponent darajasi: Landed Cost Voucher'larning item-ulushlari
  (applicable_charges) — yangi tizimda har Доп. расход qatori = alohida
  manual-LCV, ulushlar aynan saqlanadi; LCV taxes'dagi custom_dop_rasxod_row /
  custom_distribution_basis maydonlari qaysi rasxod-qatordan va qaysi usul
  bilan kelganini aniq aytadi.
- "Фарқ" ustuni (yashirin, faqat nol bo'lmasa bo'yaladi): komponentlar
  yig'indisi item'ning avtoritativ jamisiga mos kelmasa darhol ko'rinadi.

Eski (bir-LCV-ko'p-soliq) hujjatlar uchun fallback: voucher ichida soliq
summalari nisbatida chiziqli bo'linadi (ERPNext o'zi ham shunday taqsimlagan).
"""

import re

import frappe
from frappe import _
from frappe.utils import flt


BASIS_RE = re.compile(r"\[(Qty|Amount|Kg)\]\s*$")


def execute(filters=None):
    if not filters:
        return [], []

    columns = get_columns()
    data = get_data(filters)
    summary_html = get_summary_html(data)

    return columns, data, summary_html


def get_columns():
    return [
        {"fieldname": "component", "label": _("Товар / Таннарх компоненти"), "fieldtype": "Data", "width": 280},
        {"fieldname": "purchase_invoice", "label": _("Ҳужжат №"), "fieldtype": "Link", "options": "Purchase Invoice", "width": 125},
        {"fieldname": "posting_date", "label": _("Сана"), "fieldtype": "Date", "width": 85},
        {"fieldname": "supplier", "label": _("Таъминотчи"), "fieldtype": "Link", "options": "Supplier", "width": 145},
        {"fieldname": "qty", "label": _("Миқдор"), "fieldtype": "Float", "precision": 2, "width": 75},
        {"fieldname": "stock_uom", "label": _("Ў.б."), "fieldtype": "Data", "width": 55},
        {"fieldname": "total_kg", "label": _("Жами кг"), "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "basis", "label": _("Усул"), "fieldtype": "Data", "width": 75},
        {"fieldname": "ratio_pct", "label": _("Товар улуши %"), "fieldtype": "Percent", "width": 100},
        {"fieldname": "amount", "label": _("Сумма"), "fieldtype": "Currency", "width": 130},
        {"fieldname": "per_unit", "label": _("1 донага"), "fieldtype": "Currency", "width": 110},
        {"fieldname": "cost_pct", "label": _("Таннархдаги улуши %"), "fieldtype": "Percent", "width": 120},
        {"fieldname": "expense_account", "label": _("Харажат счети"), "fieldtype": "Link", "options": "Account", "width": 170, "hidden": 1},
        {"fieldname": "farq", "label": _("Фарқ (текшир)"), "fieldtype": "Currency", "width": 110, "hidden": 1},
        {"fieldname": "parent_component", "label": "", "fieldtype": "Data", "width": 0, "hidden": 1},
        {"fieldname": "item_code", "label": _("Товар коди"), "fieldtype": "Link", "options": "Item", "width": 110, "hidden": 1},
        {"fieldname": "indent", "label": "", "fieldtype": "Int", "width": 0, "hidden": 1},
        {"fieldname": "dop_supplier", "label": "", "fieldtype": "Data", "width": 0, "hidden": 1},
    ]


def get_data(filters):
    pi_rows = get_candidate_invoices(filters)
    if not pi_rows:
        return []

    pi_names = [r.name for r in pi_rows]
    items_by_pi = group_by(get_items_for_invoices(pi_names), "purchase_invoice")
    lcv_map = get_lcv_components(pi_names)

    rows = []
    for pi in pi_rows:
        rows.extend(build_rows_for_invoice(pi, items_by_pi.get(pi.name, []), lcv_map.get(pi.name, [])))

    # Filtrlar hisob-kitobdan KEYIN (taqsimot raqamlari to'liq hujjat
    # asosida — filtr ularni buzmasligi kerak). Daraxt butunligi saqlanadi:
    # item filtri — L0+bolalari; dop-ta'minotchi filtri — mos L1 + ota-L0.
    if filters.get("item"):
        rows = [r for r in rows if r.get("item_code") == filters["item"]]

    if filters.get("dop_rasxod_supplier"):
        keep_parents = {
            r["parent_component"]
            for r in rows
            if r["indent"] == 1 and r.get("dop_supplier") == filters["dop_rasxod_supplier"]
        }
        rows = [
            r
            for r in rows
            if (r["indent"] == 0 and r["component"] in keep_parents)
            or (r["indent"] == 1 and r.get("parent_component") in keep_parents
                and (r.get("dop_supplier") == filters["dop_rasxod_supplier"] or not r.get("dop_supplier")))
        ]

    return rows


def build_rows_for_invoice(pi, pi_items, lcv_components):
    """Bitta PI uchun daraxt-qatorlar: har item L0 + komponentlar L1."""
    # komponentlar item-qator (pii.name) bo'yicha
    comp_by_item = {}
    for comp in lcv_components:
        comp_by_item.setdefault(comp["pi_item_row"], []).append(comp)

    rows = []
    for it in pi_items:
        total_cost = flt(it.base_net_amount) + flt(it.item_tax_amount) + flt(it.landed_cost_voucher_amount)
        qty = flt(it.qty) or 1
        total_kg = flt(it.weight_per_unit) * flt(it.stock_qty or it.qty)
        l0_key = f"{it.item_name} — {pi.name}#{it.idx}"

        children = []

        # 1) Asosiy xarid qiymati
        children.append({
            "component": _("Харид нархи (асос)"),
            "basis": None,
            "ratio_pct": None,
            "amount": flt(it.base_net_amount),
            "per_unit": flt(it.base_net_amount) / qty,
            "cost_pct": (flt(it.base_net_amount) / total_cost * 100) if total_cost else None,
            "expense_account": None,
            "dop_supplier": None,
        })

        # 2) Valyuatsiya solig'i (bo'lsa)
        if flt(it.item_tax_amount):
            children.append({
                "component": _("Валюация солиғи"),
                "basis": None,
                "ratio_pct": None,
                "amount": flt(it.item_tax_amount),
                "per_unit": flt(it.item_tax_amount) / qty,
                "cost_pct": flt(it.item_tax_amount) / total_cost * 100 if total_cost else None,
                "expense_account": None,
                "dop_supplier": None,
            })

        # 3) Har bir Доп. расход komponenti (LCV'dan — avtoritativ)
        for comp in comp_by_item.get(it.pi_item_row, []):
            label = comp["description"] or _("Доп. расход")
            if comp["supplier"]:
                label = f"{label} · {comp['supplier']}"
            children.append({
                "component": label,
                "basis": comp["basis"],
                "ratio_pct": (comp["amount"] / comp["tax_total"] * 100) if comp["tax_total"] else None,
                "amount": comp["amount"],
                "per_unit": comp["amount"] / qty,
                "cost_pct": comp["amount"] / total_cost * 100 if total_cost else None,
                "expense_account": comp["expense_account"],
                "dop_supplier": comp["supplier"],
            })

        components_sum = sum(flt(c["amount"]) for c in children)
        farq = flt(total_cost - components_sum, 2)

        rows.append({
            "component": l0_key,
            "purchase_invoice": pi.name,
            "posting_date": pi.posting_date,
            "supplier": pi.supplier,
            "item_code": it.item_code,
            "qty": it.qty,
            "stock_uom": it.stock_uom,
            "total_kg": total_kg or None,
            "basis": None,
            "ratio_pct": None,
            "amount": total_cost,
            "per_unit": flt(it.valuation_rate) if flt(it.valuation_rate) else (total_cost / qty),
            "cost_pct": (flt(it.landed_cost_voucher_amount) / total_cost * 100) if total_cost else None,
            "expense_account": None,
            "farq": farq if abs(farq) >= 0.01 else 0,
            "parent_component": None,
            "indent": 0,
            "dop_supplier": None,
        })

        for child in children:
            rows.append({
                "purchase_invoice": None,
                "posting_date": None,
                "supplier": None,
                "item_code": it.item_code,
                "qty": None,
                "stock_uom": None,
                "total_kg": None,
                "farq": 0,
                "parent_component": l0_key,
                "indent": 1,
                **child,
            })

    return rows


def get_lcv_components(pi_names):
    """PI item-qatori bo'yicha aniq Доп. расход komponentlari (LCV'lardan).

    Qaytadi: {pi_name: [ {pi_item_row, supplier, description, basis,
                          expense_account, amount, tax_total}, ... ]}
    """
    lcvs = frappe.db.sql("""
        select lcpr.receipt_document as pi, lcv.name as lcv,
               lcv.distribute_charges_based_on as lcv_mode
        from `tabLanded Cost Purchase Receipt` lcpr
        join `tabLanded Cost Voucher` lcv on lcv.name = lcpr.parent
        where lcpr.receipt_document in %(pi_names)s
          and lcpr.receipt_document_type = 'Purchase Invoice'
          and lcv.docstatus = 1
    """, {"pi_names": pi_names}, as_dict=True)
    if not lcvs:
        return {}

    lcv_names = [l.lcv for l in lcvs]
    taxes = group_by(frappe.db.sql("""
        select parent as lcv, idx, expense_account, description, amount,
               custom_dop_rasxod_row, custom_distribution_basis
        from `tabLanded Cost Taxes and Charges`
        where parent in %(lcvs)s order by parent, idx
    """, {"lcvs": lcv_names}, as_dict=True), "lcv")
    lcv_items = group_by(frappe.db.sql("""
        select parent as lcv, purchase_receipt_item, applicable_charges
        from `tabLanded Cost Item`
        where parent in %(lcvs)s order by parent, idx
    """, {"lcvs": lcv_names}, as_dict=True), "lcv")

    # Доп. расход qatorlari (ta'minotchi/tavsif/usul uchun)
    dop_row_names = [t.custom_dop_rasxod_row for tl in taxes.values() for t in tl if t.custom_dop_rasxod_row]
    dop_rows = {}
    if dop_row_names:
        for d in frappe.db.sql("""
            select name, supplier, description, distribute_based_on
            from `tabSuviner Dop Rasxod` where name in %(names)s
        """, {"names": dop_row_names}, as_dict=True):
            dop_rows[d.name] = d

    result = {}
    for l in lcvs:
        l_taxes = taxes.get(l.lcv, [])
        l_items = lcv_items.get(l.lcv, [])
        tax_total = sum(flt(t.amount) for t in l_taxes)
        if not l_taxes or not l_items:
            continue

        for t in l_taxes:
            supplier, description, basis = describe_tax_row(t, l.lcv_mode, dop_rows)
            for li in l_items:
                if len(l_taxes) == 1:
                    # Yangi tizim (manual, bitta soliq) — aynan saqlangan ulush.
                    share = flt(li.applicable_charges)
                else:
                    # Eski uslub: voucher ichida soliq summalari nisbatida
                    # chiziqli bo'linadi (ERPNext taqsimoti ham chiziqli edi).
                    share = flt(flt(li.applicable_charges) * flt(t.amount) / tax_total, 2) if tax_total else 0
                if not share:
                    continue
                result.setdefault(l.pi, []).append({
                    "pi_item_row": li.purchase_receipt_item,
                    "supplier": supplier,
                    "description": description,
                    "basis": basis,
                    "expense_account": t.expense_account,
                    "amount": share,
                    "tax_total": flt(t.amount),
                })
    return result


def describe_tax_row(tax, lcv_mode, dop_rows):
    """LCV soliq-qatoridan (ta'minotchi, tavsif, usul)ni aniqlaydi."""
    dop = dop_rows.get(tax.custom_dop_rasxod_row)
    if dop:
        basis = tax.custom_distribution_basis or dop.distribute_based_on or lcv_mode
        return dop.supplier, dop.description, basis

    # Fallback (eski hujjatlar): "Supplier: Desc [Basis]" formatini o'qiymiz.
    desc = tax.description or ""
    basis_match = BASIS_RE.search(desc)
    basis = tax.custom_distribution_basis or (basis_match.group(1) if basis_match else lcv_mode)
    desc = BASIS_RE.sub("", desc).strip()
    supplier, _, rest = desc.partition(":")
    if rest:
        return supplier.strip(), rest.strip(), basis
    return None, desc or None, basis


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
        select pi.name, pi.posting_date, pi.company, pi.supplier
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
               pii.item_code, pii.item_name, pii.qty, pii.stock_qty, pii.stock_uom,
               pii.weight_per_unit,
               pii.base_amount, pii.base_net_amount, pii.item_tax_amount,
               pii.landed_cost_voucher_amount, pii.valuation_rate
        from `tabPurchase Invoice Item` pii
        where pii.parent in %(pi_names)s
        order by pii.parent, pii.idx
    """, {"pi_names": pi_names}, as_dict=True)


def get_summary_html(data):
    if not data:
        return ""

    l0 = [r for r in data if r.get("indent") == 0]
    l1 = [r for r in data if r.get("indent") == 1]

    total_base = sum(flt(r["amount"]) for r in l1 if r["component"] == _("Харид нархи (асос)"))
    total_tax = sum(flt(r["amount"]) for r in l1 if r["component"] == _("Валюация солиғи"))
    dop_components = [r for r in l1 if r["component"] not in (_("Харид нархи (асос)"), _("Валюация солиғи"))]
    total_dop = sum(flt(r["amount"]) for r in dop_components)
    total_final = sum(flt(r["amount"]) for r in l0)
    dop_pct = (total_dop / total_final * 100) if total_final else 0
    farq_count = sum(1 for r in l0 if abs(flt(r.get("farq"))) >= 0.01)

    # Harajat turlari kesimi
    by_type = {}
    for r in dop_components:
        key = r["component"]
        agg = by_type.setdefault(key, {"amount": 0.0, "basis": r.get("basis")})
        agg["amount"] += flt(r["amount"])
    type_rows = "".join(
        f"""<tr>
            <td style="padding: 8px 10px; border: 1px solid #ddd;">{frappe.utils.escape_html(name)}</td>
            <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: center;">{vals['basis'] or ''}</td>
            <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right;">{flt(vals['amount']):,.2f}</td>
            <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right;">{(vals['amount'] / total_dop * 100) if total_dop else 0:,.1f}%</td>
        </tr>"""
        for name, vals in sorted(by_type.items(), key=lambda kv: -kv[1]["amount"])
    )

    farq_html = ""
    if farq_count:
        farq_html = f"""<div style="margin-top:8px;padding:8px 12px;background:#fdecea;border:1px solid #e57373;border-radius:4px;color:#b71c1c;">
            ⚠ {farq_count} {_("та товарда компонентлар йиғиндиси якуний таннархга мос эмас («Фарқ» устунини ёқиб кўринг) — LCV қўлда ўзгартирилган ёки ўчирилган бўлиши мумкин.")}</div>"""

    def fmt(val):
        return f"{flt(val):,.2f}"

    return f"""
    <div style="margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 5px;">
        <table style="width: 100%; border-collapse: collapse; background: white; margin-bottom: 12px;">
            <tbody>
                <tr><td style="padding: 8px 10px; border: 1px solid #ddd; font-weight: 500; width: 60%;">{_("Умумий харид қиймати")}</td>
                    <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right;">{fmt(total_base)}</td></tr>
                <tr style="background:#fafafa;"><td style="padding: 8px 10px; border: 1px solid #ddd; font-weight: 500;">{_("Умумий валюация солиғи")}</td>
                    <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right;">{fmt(total_tax)}</td></tr>
                <tr><td style="padding: 8px 10px; border: 1px solid #ddd; font-weight: 500;">{_("Умумий Доп. расход")}</td>
                    <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right;">{fmt(total_dop)}</td></tr>
                <tr style="background:#fafafa;"><td style="padding: 8px 10px; border: 1px solid #ddd; font-weight: bold;">{_("Якуний таннарх")}</td>
                    <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right; font-weight: bold;">{fmt(total_final)}</td></tr>
                <tr><td style="padding: 8px 10px; border: 1px solid #ddd; font-weight: 500;">{_("Доп. расходнинг таннархдаги улуши")}</td>
                    <td style="padding: 8px 10px; border: 1px solid #ddd; text-align: right;">{dop_pct:,.1f}%</td></tr>
            </tbody>
        </table>
        <div style="font-weight: 600; margin: 6px 0;">{_("Доп. расход турлари кесими")}</div>
        <table style="width: 100%; border-collapse: collapse; background: white;">
            <thead><tr style="background-color: #f0f0f0;">
                <th style="padding: 8px 10px; text-align: left; border: 1px solid #ddd;">{_("Харажат тури")}</th>
                <th style="padding: 8px 10px; text-align: center; border: 1px solid #ddd;">{_("Усул")}</th>
                <th style="padding: 8px 10px; text-align: right; border: 1px solid #ddd;">{_("Сумма")}</th>
                <th style="padding: 8px 10px; text-align: right; border: 1px solid #ddd;">{_("Улуши")}</th>
            </tr></thead>
            <tbody>{type_rows or f'<tr><td colspan="4" style="padding:8px 10px;border:1px solid #ddd;">{_("Доп. расход йўқ")}</td></tr>'}</tbody>
        </table>
        {farq_html}
    </div>
    """
