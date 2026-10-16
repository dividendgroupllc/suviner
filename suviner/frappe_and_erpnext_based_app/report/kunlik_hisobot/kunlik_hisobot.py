# Copyright (c) 2026, Suviner and contributors
# For license information, please see license.txt
"""
Kunlik Hisobot — tanlangan kun (yoki davr) bo'yicha BARCHA tranzaksiyalar:

- Sotuv / Qaytarish  — Sales Invoice (docstatus = 1);
- Prixod / Rasxod / Peremesheniya / Konvertatsiya — Kassa (docstatus = 1).

Yuqorida jami kartochkalar (qancha sotuv, rasxod, peremesheniya...) VALYUTA
bo'yicha alohida chiqadi — turli valyutadagi summalar bitta songa qo'shilmaydi.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


TX_SOTUV = "Sotuv"
TX_QAYTARISH = "Qaytarish"
TX_PRIXOD = "Prixod"
TX_RASXOD = "Rasxod"
TX_PEREMESHENIYA = "Peremesheniya"
TX_KONVERTATSIYA = "Konvertatsiya"

# Kassa.transaction_type -> hisobotdagi tur
KASSA_TYPES = {
    "Приход": TX_PRIXOD,
    "Расход": TX_RASXOD,
    "Перемещения": TX_PEREMESHENIYA,
    "Конвертация": TX_KONVERTATSIYA,
}

# Kartochkalar tartibi va rangi (Sotuv/Rasxod/Peremesheniya doim ko'rinadi)
SUMMARY_TYPES = [
    (TX_SOTUV, "Green", True),
    (TX_QAYTARISH, "Orange", False),
    (TX_RASXOD, "Red", True),
    (TX_PEREMESHENIYA, "Blue", True),
    (TX_PRIXOD, "Green", False),
    (TX_KONVERTATSIYA, "Purple", False),
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    chosen = _as_list(filters.get("transaction_type"))
    data = []
    if not chosen or set(chosen) & {TX_SOTUV, TX_QAYTARISH}:
        data += get_sales(filters)
    if not chosen or set(chosen) & set(KASSA_TYPES.values()):
        data += get_kassa(filters)

    if chosen:
        data = [d for d in data if d["tx_type"] in chosen]

    data.sort(key=lambda d: (d["date"], d["time"] or "", d["name"]))

    company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
    return get_columns(), data, None, None, get_summary(data, company_currency)


def validate_filters(filters):
    if not filters.get("company"):
        frappe.throw(_("Kompaniyani tanlang"))
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("Sana oralig'i majburiy"))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("Boshlanish sanasi tugash sanasidan katta bo'lishi mumkin emas"))


def _as_list(value):
    """MultiSelectList qiymatini ro'yxatga keltiradi (bo'sh -> [])."""
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = frappe.parse_json(value)
        except Exception:
            parsed = None
        return parsed if isinstance(parsed, list) else [value]
    return list(value)


def get_columns():
    return [
        {"fieldname": "date", "label": _("Sana"), "fieldtype": "Date", "width": 95},
        {"fieldname": "time", "label": _("Vaqt"), "fieldtype": "Data", "width": 65},
        {"fieldname": "tx_type", "label": _("Turi"), "fieldtype": "Data", "width": 120},
        {"fieldname": "qayerdan", "label": _("Qayerdan"), "fieldtype": "Data", "width": 200},
        {"fieldname": "qayerga", "label": _("Qayerga"), "fieldtype": "Data", "width": 200},
        {"fieldname": "currency", "label": _("Valyuta"), "fieldtype": "Data", "width": 70},
        {"fieldname": "kirim", "label": _("Kirim"), "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "chiqim", "label": _("Chiqim"), "fieldtype": "Float", "precision": 2, "width": 130},
        {"fieldname": "remarks", "label": _("Izoh"), "fieldtype": "Data", "width": 200},
        {"fieldname": "doctype_name", "label": _("Hujjat turi"), "fieldtype": "Data", "hidden": 1},
        {"fieldname": "name", "label": _("Hujjat"), "fieldtype": "Dynamic Link", "options": "doctype_name", "width": 160},
    ]


def get_sales(filters):
    rows = frappe.db.sql("""
        select si.name, si.posting_date as date, time_format(si.posting_time, '%%H:%%i') as time,
               si.is_return, si.currency, si.customer, si.customer_name,
               if(ifnull(si.disable_rounded_total, 0) = 0 and ifnull(si.rounded_total, 0) != 0,
                  si.rounded_total, si.grand_total) as total,
               si.remarks
        from `tabSales Invoice` si
        where si.docstatus = 1
          and si.company = %(company)s
          and si.posting_date between %(from_date)s and %(to_date)s
    """, filters, as_dict=True)

    if not rows:
        return []

    # Har bir chek bo'yicha to'lov turlari (Naqd, Plastik ...)
    payments = {}
    for p in frappe.db.sql("""
        select parent, mode_of_payment, sum(amount) as amount
        from `tabSales Invoice Payment`
        where parent in %(names)s and amount != 0
        group by parent, mode_of_payment
    """, {"names": [r.name for r in rows]}, as_dict=True):
        payments.setdefault(p.parent, []).append(p.mode_of_payment)

    data = []
    for r in rows:
        total = flt(r.total)
        is_return = r.is_return or total < 0
        kassa = ", ".join(payments.get(r.name, [])) or _("Nasiya")
        mijoz = r.customer_name or r.customer
        data.append({
            "date": r.date,
            "time": r.time,
            "tx_type": TX_QAYTARISH if is_return else TX_SOTUV,
            # Sotuvda pul mijozdan kassaga, qaytarishda kassadan mijozga
            "qayerdan": kassa if is_return else mijoz,
            "qayerga": mijoz if is_return else kassa,
            "currency": r.currency,
            "kirim": None if is_return else total,
            "chiqim": abs(total) if is_return else None,
            "remarks": r.remarks if r.remarks and r.remarks != "No Remarks" else None,
            "doctype_name": "Sales Invoice",
            "name": r.name,
        })
    return data


def get_kassa(filters):
    rows = frappe.db.sql("""
        select k.name, k.date, time_format(k.time, '%%H:%%i') as time, k.transaction_type,
               k.mode_of_payment, k.mode_of_payment_to,
               k.cash_account_currency, k.cash_account_to_currency,
               k.amount, k.debit_amount, k.credit_amount,
               k.party_type, k.party, k.party_name,
               k.expense_account, k.expense_account_name,
               k.remarks
        from `tabKassa` k
        where k.docstatus = 1
          and k.company = %(company)s
          and k.date between %(from_date)s and %(to_date)s
    """, filters, as_dict=True)

    data = []
    for r in rows:
        tx_type = KASSA_TYPES.get(r.transaction_type, r.transaction_type)
        row = {
            "date": r.date,
            "time": r.time,
            "tx_type": tx_type,
            "qayerdan": r.mode_of_payment,
            "qayerga": r.mode_of_payment_to,
            "currency": r.cash_account_currency,
            "kirim": None,
            "chiqim": None,
            "remarks": r.remarks,
            "doctype_name": "Kassa",
            "name": r.name,
        }

        if tx_type == TX_PEREMESHENIYA:
            row["chiqim"] = flt(r.amount) or flt(r.debit_amount)
        elif tx_type == TX_KONVERTATSIYA:
            row["chiqim"] = flt(r.debit_amount) or flt(r.amount)
            target = flt(r.credit_amount)
            if target:
                row["qayerga"] = "{0} ({1} {2})".format(
                    r.mode_of_payment_to or "",
                    frappe.format(target, {"fieldtype": "Float", "precision": 2}),
                    r.cash_account_to_currency or "",
                ).strip()
        else:
            kontragent = r.party_name or r.party or r.expense_account_name or r.expense_account
            if r.party_type and (r.party_name or r.party):
                kontragent = f"{kontragent} ({r.party_type})"
            if tx_type == TX_PRIXOD:
                # pul kontragentdan kassaga keladi
                row["qayerdan"], row["qayerga"] = kontragent, r.mode_of_payment
                row["kirim"] = flt(r.amount)
            else:
                row["qayerga"] = kontragent
                row["chiqim"] = flt(r.amount)

        data.append(row)
    return data


def get_summary(data, company_currency):
    # {tur: {valyuta: summa}}
    totals = {}
    for d in data:
        amount = flt(d["kirim"]) or flt(d["chiqim"])
        bucket = totals.setdefault(d["tx_type"], {})
        bucket[d["currency"]] = bucket.get(d["currency"], 0) + amount

    summary = []
    for tx_type, indicator, always in SUMMARY_TYPES:
        by_currency = totals.get(tx_type)
        if not by_currency:
            if always:
                summary.append({
                    "label": _(tx_type),
                    "value": 0,
                    "datatype": "Currency",
                    "currency": company_currency,
                    "indicator": indicator,
                })
            continue
        for currency, value in sorted(by_currency.items()):
            summary.append({
                "label": f"{_(tx_type)} ({currency})" if len(by_currency) > 1 else _(tx_type),
                "value": value,
                "datatype": "Currency",
                "currency": currency,
                "indicator": indicator,
            })

    summary.append({
        "label": _("Tranzaksiyalar soni"),
        "value": len(data),
        "datatype": "Int",
        "indicator": "Grey",
    })
    return summary
