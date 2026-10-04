# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""Доп. расход тақсимоти — partiya (Purchase Invoice) bo'yicha har bir
qo'shimcha xarajat qaysi tovarga qancha tushganini MATRITSA ko'rinishida
ko'rsatadi (avval Google Sheet'da qo'lda yuritilgan jadval uslubida):

  Партия | Сони | Жами сумма | Завод нархи | Жами доп. | <har Счет расходов> ... | Доп. %

- Har partiya uchun bitta JAMI qatori — summalar butun partiya bo'yicha;
- tovar qatorlari — 1 dona uchun (yoki «Итого» rejimida qator jami);
- ustunlar = Доп. расход qatorining «Счет расходов»i (istalgan Expense hisobi —
  har xil xarajatlar o'z hisobida). Erkin matnli «Вид расхода» bo'yicha EMAS — u har PI'da har xil yozilib, ustunlar bo'linib/qo'shilib
  ketardi (2026-10-03). Bir hisobdagi bir necha qator (masalan Деклорант
  400 USD + 800 000 UZS) bitta ustunda qo'shiladi.

Valyuta: BITTA partiya tanlansa — hujjat valyutasi (USD invoys — USD'da, kurs
PI'niki) yoki kompaniya valyutasi; bir nechta partiyada — FAQAT kompaniya
valyutasi (USD va UZS partiyalar bir ustunda aralashmasin) va oxirida umumiy JAMI.

MANBA — Tannarx Shakllanishi bilan bir xil: tovar ulushlari LCV'lardan
(get_lcv_components) — kompaniya valyutasida omborga tushgan tannarx bilan
aynan teng; Suviner Dop Rasxod qatorlari faqat ustunlar tartibi uchun.
"""

import frappe
from frappe import _
from frappe.utils import flt

from suviner.frappe_and_erpnext_based_app.report.tannarx_shakllanishi.tannarx_shakllanishi import (
    get_lcv_components,
    group_by,
)

PER_UNIT = "На 1 единицу"
CURRENCY_INVOICE = "Валюта счета"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    invoices = get_invoices(filters)
    if not invoices:
        return get_columns([], {}, False), []

    pi_names = [pi.name for pi in invoices]
    items_by_pi = group_by(get_items(pi_names), "purchase_invoice")
    lcv_by_pi = get_lcv_components(pi_names)
    dop_by_pi = group_by(get_dop_rows(pi_names), "parent")

    single = bool(filters.get("purchase_invoice"))
    in_invoice_currency = single and (filters.get("currency_mode") or CURRENCY_INVOICE) == CURRENCY_INVOICE
    per_unit = (filters.get("row_mode") or PER_UNIT) == PER_UNIT

    blocks = [
        build_block(pi, items_by_pi.get(pi.name, []), lcv_by_pi.get(pi.name, []),
                    dop_by_pi.get(pi.name, []), in_invoice_currency)
        for pi in invoices
    ]

    # Ustunlar — barcha partiyalar bo'yicha hisoblar birlashmasi, birinchi
    # uchragan tartibda (dop-qator idx bo'yicha).
    accounts = []
    for block in blocks:
        for account in block["accounts"]:
            if account not in accounts:
                accounts.append(account)
    has_tax = any(block["has_tax"] for block in blocks)

    columns = get_columns(accounts, account_labels(accounts), has_tax)
    data = []
    for block in blocks:
        data.extend(block_rows(block, accounts, per_unit))
    if len(blocks) > 1:
        data.append(grand_total_row(blocks, accounts))

    return columns, data


def cost_fieldname(index):
    return f"cost_{index}"


def account_labels(accounts):
    """Ustun nomi — hisobning account_name'i (" - S" qo'shimchasisiz); ikki
    hisob nomi bir xil bo'lsa, to'liq nomi."""
    names = dict(frappe.get_all(
        "Account", filters={"name": ["in", accounts or [""]]}, fields=["name", "account_name"], as_list=True
    ))
    labels = {a: names.get(a) or a for a in accounts}
    seen = {}
    for label in labels.values():
        seen[label] = seen.get(label, 0) + 1
    return {a: (a if seen[label] > 1 else label) for a, label in labels.items()}


def get_columns(accounts, labels, has_tax):
    columns = [
        {"fieldname": "partiya", "label": _("Партия / Товар"), "fieldtype": "Data", "width": 260},
        {"fieldname": "purchase_invoice", "label": _("Ҳужжат"), "fieldtype": "Link",
         "options": "Purchase Invoice", "width": 140},
        {"fieldname": "posting_date", "label": _("Сана"), "fieldtype": "Date", "width": 90},
        {"fieldname": "qty", "label": _("Сони"), "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "total", "label": _("Жами сумма"), "fieldtype": "Float", "precision": 2, "width": 120},
        {"fieldname": "factory", "label": _("Завод нархи"), "fieldtype": "Float", "precision": 2, "width": 120},
    ]
    if has_tax:
        columns.append({"fieldname": "tax", "label": _("Солиқ (валюация)"), "fieldtype": "Float",
                        "precision": 2, "width": 110})
    columns.append({"fieldname": "dop_total", "label": _("Жами доп. расход"), "fieldtype": "Float",
                    "precision": 2, "width": 120})
    for index, account in enumerate(accounts):
        columns.append({"fieldname": cost_fieldname(index), "label": labels[account], "fieldtype": "Float",
                        "precision": 2, "width": 120})
    columns += [
        {"fieldname": "dop_pct", "label": _("Доп. расход %"), "fieldtype": "Percent", "width": 105},
        {"fieldname": "currency", "label": _("Валюта"), "fieldtype": "Data", "width": 65},
        {"fieldname": "parent_partiya", "label": "", "fieldtype": "Data", "hidden": 1},
        {"fieldname": "indent", "label": "", "fieldtype": "Int", "hidden": 1},
    ]
    return columns


def get_invoices(filters):
    conditions = ["pi.docstatus = 1", "pi.custom_dop_rasxod = 1"]
    values = {}
    if filters.get("purchase_invoice"):
        conditions.append("pi.name = %(purchase_invoice)s")
        values["purchase_invoice"] = filters.purchase_invoice
    else:
        conditions.append("pi.posting_date between %(from_date)s and %(to_date)s")
        values.update(from_date=filters.get("from_date"), to_date=filters.get("to_date"))
    if filters.get("company"):
        conditions.append("pi.company = %(company)s")
        values["company"] = filters.company
    if filters.get("supplier"):
        conditions.append("pi.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    return frappe.db.sql(f"""
        select pi.name, pi.posting_date, pi.supplier, pi.supplier_name, pi.company,
               pi.currency, pi.conversion_rate, c.default_currency as company_currency
        from `tabPurchase Invoice` pi
        join `tabCompany` c on c.name = pi.company
        where {" and ".join(conditions)}
        order by pi.posting_date, pi.name
    """, values, as_dict=True)


def get_items(pi_names):
    return frappe.db.sql("""
        select name as pi_item_row, parent as purchase_invoice, idx, item_code, item_name,
               qty, net_amount, base_net_amount, item_tax_amount
        from `tabPurchase Invoice Item`
        where parent in %(pi_names)s
        order by parent, idx
    """, {"pi_names": pi_names}, as_dict=True)


def get_dop_rows(pi_names):
    return frappe.db.sql("""
        select parent, idx, expense_account
        from `tabSuviner Dop Rasxod`
        where parent in %(pi_names)s and parenttype = 'Purchase Invoice'
        order by parent, idx
    """, {"pi_names": pi_names}, as_dict=True)


def build_block(pi, items, components, dop_rows, in_invoice_currency):
    """Bitta partiya: tovar qatorlari va hisoblar bo'yicha ulushlar, hisobot valyutasida."""
    currency = pi.currency if in_invoice_currency else pi.company_currency
    # LCV summalari kompaniya valyutasida — hisobot valyutasiga o'tkazish.
    rate_to_company = (flt(pi.conversion_rate) or 1) if in_invoice_currency else 1

    # Ustun tartibi — dop-qatorlar idx bo'yicha (LCV so'rovi tartib kafolatlamaydi).
    accounts = []
    for row in dop_rows:
        if row.expense_account and row.expense_account not in accounts:
            accounts.append(row.expense_account)

    # Tovar ulushlari (LCV) — PI item qatori → {hisob: summa}
    alloc = {}
    for comp in components:
        account = comp["expense_account"]
        if account not in accounts:  # eski LCV (dop-qatorsiz)
            accounts.append(account)
        per_item = alloc.setdefault(comp["pi_item_row"], {})
        per_item[account] = flt(per_item.get(account)) + flt(comp["amount"]) / rate_to_company

    rows = []
    for it in items:
        costs = alloc.get(it.pi_item_row, {})
        rows.append({
            "label": f"{it.idx}. {it.item_name or it.item_code}",
            "qty": flt(it.qty),
            "factory": flt(it.net_amount) if in_invoice_currency else flt(it.base_net_amount),
            "tax": flt(it.item_tax_amount) / rate_to_company,
            "costs": costs,
            "dop_total": sum(costs.values()),
        })

    cost_totals = {a: sum(flt(r["costs"].get(a)) for r in rows) for a in accounts}
    return {
        "pi": pi,
        "currency": currency,
        "rows": rows,
        "accounts": [a for a in accounts if cost_totals[a]],
        "cost_totals": cost_totals,
        "factory_total": sum(r["factory"] for r in rows),
        "tax_total": sum(r["tax"] for r in rows),
        "has_tax": any(flt(r["tax"]) for r in rows),
    }


def block_rows(block, accounts, per_unit):
    pi = block["pi"]
    # Daraxt kaliti — noyob bo'lishi shart (bir kunda bir ta'minotchidan 2 partiya).
    head_label = f"{pi.name} — {pi.supplier_name or pi.supplier}"
    factory_total = block["factory_total"]
    dop_total = sum(block["cost_totals"].values())

    head = {
        "partiya": head_label,
        "purchase_invoice": pi.name,
        "posting_date": pi.posting_date,
        "qty": sum(r["qty"] for r in block["rows"]),
        "factory": factory_total,
        "tax": block["tax_total"],
        "dop_total": dop_total,
        "total": factory_total + block["tax_total"] + dop_total,
        "dop_pct": (dop_total / factory_total * 100) if factory_total else 0,
        "currency": block["currency"],
        "parent_partiya": None,
        "indent": 0,
    }
    for index, account in enumerate(accounts):
        head[cost_fieldname(index)] = block["cost_totals"].get(account) or None

    out = [head]
    for r in block["rows"]:
        divisor = r["qty"] if per_unit and r["qty"] else 1
        line = {
            "partiya": r["label"],
            "purchase_invoice": None,
            "posting_date": None,
            "qty": r["qty"],
            "factory": r["factory"] / divisor,
            "tax": r["tax"] / divisor,
            "dop_total": r["dop_total"] / divisor,
            "total": (r["factory"] + r["tax"] + r["dop_total"]) / divisor,
            "dop_pct": (r["dop_total"] / r["factory"] * 100) if r["factory"] else 0,
            "currency": block["currency"],
            "parent_partiya": head_label,
            "indent": 1,
        }
        for index, account in enumerate(accounts):
            value = r["costs"].get(account)
            line[cost_fieldname(index)] = (flt(value) / divisor) if value else None
        out.append(line)
    return out


def grand_total_row(blocks, accounts):
    """Bir nechta partiya — umumiy jami (hammasi kompaniya valyutasida).
    Сони yig'ilmaydi: turli tovar va o'lchov birliklari qo'shilib ma'nosiz bo'lardi."""
    factory = sum(b["factory_total"] for b in blocks)
    tax = sum(b["tax_total"] for b in blocks)
    dop = sum(sum(b["cost_totals"].values()) for b in blocks)
    row = {
        "partiya": _("Жами ({0} партия)").format(len(blocks)),
        "factory": factory,
        "tax": tax,
        "dop_total": dop,
        "total": factory + tax + dop,
        "dop_pct": (dop / factory * 100) if factory else 0,
        "currency": blocks[0]["currency"],
        "parent_partiya": None,
        "indent": 0,
    }
    for index, account in enumerate(accounts):
        row[cost_fieldname(index)] = sum(flt(b["cost_totals"].get(account)) for b in blocks) or None
    return row
