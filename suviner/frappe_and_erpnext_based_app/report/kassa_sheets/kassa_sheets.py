# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""
Kassa Sheets — Kassa hujjatlari uchun "varaq" hisoboti (Prodaja/Prixod Sheets
uslubida): davr bo'yicha barcha kassa operatsiyalari kassa-kitob ko'rinishida.

- Приход / Расход alohida ustunlarda (klassik kassa kitobi);
- Перемещения/Конвертация IKKI qator bo'ladi: manba kassada Расход,
  maqsad kassada Приход (har biri O'Z valyutasida) — xuddi qog'oz kassa
  kitobidagidek; filtrlar ikkala tomonni ham topadi;
"""

import frappe
from frappe import _
from frappe.utils import flt


TX_PRIXOD = "Приход"
TX_RASXOD = "Расход"
TX_TRANSFER = "Перемещения"
TX_KONV = "Конвертация"


def execute(filters=None):
    if not filters:
        return [], []

    return get_columns(filters), get_data(filters)


def get_columns(filters):
    # Ustun nomlari — Kassa doctype'dagi field-nomlar bilan AYNAN bir xil.
    cols = [
        {"fieldname": "date", "label": _("Дата"), "fieldtype": "Date", "width": 95},
        {"fieldname": "time", "label": _("Время"), "fieldtype": "Data", "width": 70},
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

    for field in ("transaction_type", "party_type"):
        chosen = _as_list(filters.get(field))
        if chosen:
            conditions.append(f"k.{field} in %({field})s")
            values[field] = chosen

    mops = _as_list(filters.get("mode_of_payment"))
    if mops:
        # transfer/konvertatsiyada maqsad kassa ham mos kelsin (qator-darajada
        # yakuniy filtr pastda)
        conditions.append("(k.mode_of_payment in %(mops)s or k.mode_of_payment_to in %(mops)s)")
        values["mops"] = mops

    if filters.get("party"):
        conditions.append("(k.party = %(party)s or k.party_name like %(party_like)s)")
        values["party"] = filters["party"]
        values["party_like"] = f"%{filters['party']}%"

    currencies = _as_list(filters.get("currency"))
    if currencies:
        conditions.append("(k.cash_account_currency in %(currencies)s or k.cash_account_to_currency in %(currencies)s)")
        values["currencies"] = currencies

    rows = frappe.db.sql(f"""
        select k.name, k.date, time_format(k.time, '%%H:%%i') as time, k.docstatus, k.transaction_type,
               k.mode_of_payment, k.mode_of_payment_to,
               k.cash_account_currency, k.cash_account_to_currency,
               k.amount, k.debit_amount, k.credit_amount,
               k.party_type, k.party, k.party_name,
               k.expense_account, k.expense_account_name,
               k.remarks, k.linked_doctype, k.linked_entry,
               k.against_invoice
        from `tabKassa` k
        where {' and '.join(conditions)}
        order by k.date, k.time, k.name
    """, values, as_dict=True)

    data = []
    for r in rows:
        base = {
            "date": r.date,
            "time": r.time,
            "name": r.name,
            "status": _("Черновик") if r.docstatus == 0 else _("Проведен"),
            "transaction_type": r.transaction_type,
            "expense_account": r.expense_account,
            "remarks": r.remarks,
            "linked": f"{r.linked_doctype}: {r.linked_entry}" if r.linked_entry else None,
            "docstatus": r.docstatus,
        }

        invoice_ref = r.against_invoice or ""

        if r.transaction_type in (TX_TRANSFER, TX_KONV) and r.mode_of_payment_to:
            # IKKI qator: manbada chiqim, maqsadda kirim — har biri o'z
            # kassasi va valyutasida. Summalar TUR bo'yicha aniq maydondan
            # olinadi (qiymat-hidlash emas: tur almashtirilganda eskirgan
            # amount qolib ketishi mumkin).
            if r.transaction_type == TX_KONV:
                chiqim = flt(r.debit_amount) or flt(r.amount)
                kirim = flt(r.credit_amount)
                # Konvertatsiyada maqsad valyuta manbanikidan farq qiladi —
                # noma'lum bo'lsa manba valyutasini YOZMAYMIZ (bo'sh qoladi).
                kirim_currency = r.cash_account_to_currency or ""
            else:
                chiqim = flt(r.amount) or flt(r.debit_amount)
                kirim = chiqim
                kirim_currency = r.cash_account_to_currency or r.cash_account_currency

            data.append({
                **base,
                "mode_of_payment": r.mode_of_payment,
                "mode_of_payment_to": f"→ {r.mode_of_payment_to}",
                "currency": r.cash_account_currency,
                "prixod": None,
                "rasxod": chiqim,
                "kontragent": invoice_ref,
            })
            # Maqsad-qator faqat real kirim bo'lsa (draft konvertatsiyada
            # credit hali 0 bo'lishi mumkin — 0.00 fantom qator chiqarmaymiz).
            if kirim:
                data.append({
                    **base,
                    "mode_of_payment": r.mode_of_payment_to,
                    "mode_of_payment_to": f"← {r.mode_of_payment}" if r.mode_of_payment else None,
                    "currency": kirim_currency,
                    "prixod": kirim,
                    "rasxod": None,
                    "kontragent": invoice_ref,
                })
        else:
            # Приход/Расход — bitta qator. Noma'lum/kelajak turlar ham xavfsiz
            # bitta chiqim-qatorga tushadi (kirim to'qib chiqarilmaydi).
            if r.transaction_type in (TX_PRIXOD, TX_RASXOD):
                summa = flt(r.amount)
                kontragent = r.party_name or r.party or r.expense_account_name or ""
                if r.party_type and (r.party_name or r.party):
                    kontragent = f"{kontragent} ({r.party_type})"
            else:
                summa = flt(r.amount) or flt(r.debit_amount)
                kontragent = ""
            if invoice_ref:
                kontragent = f"{kontragent} · {invoice_ref}" if kontragent else invoice_ref

            data.append({
                **base,
                "mode_of_payment": r.mode_of_payment,
                "mode_of_payment_to": f"→ {r.mode_of_payment_to}" if r.mode_of_payment_to else None,
                "currency": r.cash_account_currency,
                "prixod": summa if r.transaction_type == TX_PRIXOD else None,
                "rasxod": summa if r.transaction_type != TX_PRIXOD else None,
                "kontragent": kontragent,
            })

    # Qator-darajadagi yakuniy filtr: kassa/valyuta endi har qatorning
    # O'ZIGA qaraydi (transfer-kirim qatori ham to'g'ri topiladi).
    if mops:
        data = [d for d in data if d["mode_of_payment"] in mops]
    if currencies:
        data = [d for d in data if d["currency"] in currencies]

    return data
