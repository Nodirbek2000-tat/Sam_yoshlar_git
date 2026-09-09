"""«Chet eldagi tengdoshim» — davlatlar ro'yxati.

Bayroq emojilari Windows'da harf juftligi bo'lib chiqadi, shuning uchun
har bir davlatning ikki harfli kodi va rangi ishlatiladi — hamma joyda bir xil ko'rinadi.
"""

# (kod, nom, qisqartma, rang)
COUNTRIES = [
    ('usa', "AQSh", 'US', '#3c58d6'),
    ('uk', "Buyuk Britaniya", 'UK', '#1f3a93'),
    ('germany', "Germaniya", 'DE', '#2f3640'),
    ('turkey', "Turkiya", 'TR', '#d64545'),
    ('russia', "Rossiya", 'RU', '#4a6fa5'),
    ('korea', "Janubiy Koreya", 'KR', '#2f7fd6'),
    ('japan', "Yaponiya", 'JP', '#c94f6d'),
    ('china', "Xitoy", 'CN', '#d6483c'),
    ('uae', "BAA", 'AE', '#2f9e6b'),
    ('kazakhstan', "Qozog'iston", 'KZ', '#2f9fd6'),
    ('poland', "Polsha", 'PL', '#d65a7a'),
    ('italy', "Italiya", 'IT', '#3f9e63'),
    ('france', "Fransiya", 'FR', '#3a63c9'),
    ('canada', "Kanada", 'CA', '#d6564f'),
    ('malaysia', "Malayziya", 'MY', '#2f8fa8'),
    ('india', "Hindiston", 'IN', '#e08a3c'),
    ('latvia', "Latviya", 'LV', '#a8453f'),
    ('czech', "Chexiya", 'CZ', '#3f6fb5'),
    ('other', "Boshqa davlat", '??', '#5a6b80'),
]

COUNTRY_CHOICES = [(code, name) for code, name, _, _ in COUNTRIES]
COUNTRY_SHORT = {code: short for code, _, short, _ in COUNTRIES}
COUNTRY_COLORS = {code: color for code, _, _, color in COUNTRIES}
COUNTRY_NAMES = {code: name for code, name, _, _ in COUNTRIES}


def short_of(code):
    return COUNTRY_SHORT.get(code, '??')


def color_of(code):
    return COUNTRY_COLORS.get(code, '#5a6b80')
