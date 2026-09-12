# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Kassa Sheets — Kassa hujjatlari uchun "varaq" hisoboti (Prodaja/Prixod Sheets
uslubida): davr bo'yicha barcha kassa operatsiyalari kassa-kitob ko'rinishida.

- Приход / Расход alohida ustunlarda (klassik kassa kitobi);
- Перемещения/Конвертация qatorlarida summa Расход ustunida (manba kassadan
  chiqim), "Контрагент" ustunida esa qayerga o'tgani (→ maqsad kassa);
"""

import frappe
from frappe import _
from frappe.utils import flt


TX_PRIXOD = "Приход"
TX_RASXOD = "Расход"


def execute(filters=None):
    if not filters:
        return [], []

    return get_columns(filters), get_data(filters)


def get_columns(filters):
    # Ustun nomlari — Kassa doctype'dagi field-nomlar bilan AYNAN bir xil.
    cols = [
        {"fieldname": "date", "label": _("Дата"), "fieldtype": "Date", "width": 95},
        {"fieldname": "transaction_type", "label": _("Тип операции"), "fieldtype": "Data", "width": 115},
        {"fieldname": "mode_of_payment", "label": _("Способ оплаты"), "fieldtype": "Link", "options": "Mode of Payment", "width": 135},
        {"fieldname": "mode_of_payment_to", "label": _("Способ оплаты (куда)"), "fieldtype": "Data", "width": 150},
        {"fieldname": "kontragent", "label": _("Контрагент"), "fieldtype": "Data", "width": 200},
        {"fieldname": "currency", "label": _("Валюта кассы"), "fieldtype": "Data", "width": 80},
        {"fieldname": "prixod", "label": _("Приход"), "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "rasxod", "label": _("Расход"), "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "expense_account", "label": _("Счет расходов"), "fieldtype": "Link", "options": "Account", "width": 160},
        {"fieldname": "remarks", "label": _("Примечание"), "fieldtype": "Data", "width": 220},
        {"fieldname": "name", "label": _("Ҳужжат №"), "fieldtype": "Link", "options": "Kassa", "width": 150},
        {"fieldname": "linked", "label": _("Связанный документ"), "fieldtype": "Data", "width": 170},
    ]
    if filters.get("include_drafts"):
        cols.insert(2, {"fieldname": "status", "label": _("Ҳолат"), "fieldtype": "Data", "width": 90})
    return cols


def get_data(filters):
    conditions = [
        "k.company = %(company)s",
        "k.date between %(from_date)s and %(to_date)s",
    ]
    values = {
        "company": filters.get("company"),
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
    }

    if filters.get("include_drafts"):
        conditions.append("k.docstatus in (0, 1)")
    else:
        conditions.append("k.docstatus = 1")

    for field in ("transaction_type", "mode_of_payment", "party_type"):
        if filters.get(field):
            conditions.append(f"k.{field} = %({field})s")
            values[field] = filters[field]

    if filters.get("party"):
        conditions.append("(k.party = %(party)s or k.party_name like %(party_like)s)")
        values["party"] = filters["party"]
        values["party_like"] = f"%{filters['party']}%"

    if filters.get("currency"):
        conditions.append("k.cash_account_currency = %(currency)s")
        values["currency"] = filters["currency"]

    rows = frappe.db.sql(f"""
        select k.name, k.date, k.docstatus, k.transaction_type,
               k.mode_of_payment, k.mode_of_payment_to,
               k.cash_account_currency, k.cash_account_to_currency,
               k.amount, k.debit_amount, k.credit_amount,
               k.party_type, k.party, k.party_name,
               k.expense_account, k.expense_account_name,
               k.remarks, k.linked_doctype, k.linked_entry,
               k.against_invoice
        from `tabKassa` k
        where {' and '.join(conditions)}
        order by k.date, k.name
    """, values, as_dict=True)

    data = []
    for r in rows:
        # Konvertatsiyada summa debit_amount'da saqlanadi (amount 0 bo'ladi)
        summa = flt(r.amount) or flt(r.debit_amount)
        prixod = summa if r.transaction_type == TX_PRIXOD else None
        rasxod = summa if r.transaction_type != TX_PRIXOD else None

        # Kontragent — faqat Приход/Расходда; yo'nalish alohida ustunda
        kontragent = ""
        if r.transaction_type in (TX_PRIXOD, TX_RASXOD):
            kontragent = r.party_name or r.party or r.expense_account_name or ""
            if r.party_type and (r.party_name or r.party):
                kontragent = f"{kontragent} ({r.party_type})"
        if r.against_invoice:
            kontragent = f"{kontragent} · {r.against_invoice}" if kontragent else r.against_invoice

        # Qayerga (transfer/konvertatsiya): maqsad kassa, konvertatsiyada
        # qabul qilingan summa-valyuta ham ko'rsatiladi
        mop_to = r.mode_of_payment_to or ""
        if mop_to and r.transaction_type == "Конвертация" and flt(r.credit_amount):
            mop_to = f"{mop_to} ({flt(r.credit_amount):,.2f} {r.cash_account_to_currency or ''})".rstrip()

        data.append({
            "date": r.date,
            "name": r.name,
            "status": _("Черновик") if r.docstatus == 0 else _("Проведен"),
            "transaction_type": r.transaction_type,
            "mode_of_payment": r.mode_of_payment,
            "mode_of_payment_to": mop_to or None,
            "currency": r.cash_account_currency,
            "prixod": prixod,
            "rasxod": rasxod,
            "kontragent": kontragent,
            "expense_account": r.expense_account,
            "remarks": r.remarks,
            "linked": f"{r.linked_doctype}: {r.linked_entry}" if r.linked_entry else None,
            "docstatus": r.docstatus,
        })

    return data
