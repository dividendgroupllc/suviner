# Copyright (c) 2026, Sardorbek Qamchibekov and contributors
# For license information, please see license.txt
"""«Касса» linkini Transaction ID bo'limiga (reference_date yoniga) ko'chiradi
va link bor hujjatlarda matnli Cheque/Reference'ni yashiradi.

add_kassa_source_link patch'i prodda eski joylashuv bilan allaqachon bajarilgan
— yangi nomli patch execute()ni qayta chaqiradi (idempotent)."""

from suviner.custom.kassa_source_link import execute as apply_fields


def execute():
	apply_fields()
