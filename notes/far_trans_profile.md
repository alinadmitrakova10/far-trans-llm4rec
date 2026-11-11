# FAR-Trans: автоматически сформированный профиль

Команда: `python scripts/inspect_far_trans.py`. Источник: https://researchdata.gla.ac.uk/1658/.
Все количества относятся к строкам релиза, не к независимым пользователям/сделкам.
Идентификаторы сохраняются строками. Типы остальных значений — лексические, не SQL-схема.
Пропуски: пустая строка, `Not_Available`, `-` и стандартные NA-маркеры; дата `2000-01-01` проверяется отдельно.

## asset_information.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/asset_information.csv`; SHA-256: `33f9897b14087068fba53a0bc9e24a0031b096bd3ad3e977e534153f29b7a590`.

Строк: **836**; полных дубликатов: 0; некорректных CSV-записей: 0.

| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |
|---|---|---:|---|---:|---|
| ISIN | {"identifier_string": 836} | 806 | `{}` | 0 | — |
| assetName | {"string": 812, "missing_marker": 24} | 712 | `{"": 24}` | 0 | — |
| assetShortName | {"string": 835, "missing_marker": 1} | 792 | `{"": 1}` | 0 | — |
| assetCategory | {"string": 836} | 3 | `{}` | 0 | — |
| assetSubCategory | {"string": 567, "missing_marker": 269} | 11 | `{"": 269}` | 0 | — |
| marketID | {"identifier_string": 836} | 38 | `{}` | 0 | — |
| sector | {"missing_marker": 388, "string": 448} | 16 | `{"": 388}` | 0 | — |
| industry | {"missing_marker": 439, "string": 397} | 120 | `{"": 439}` | 0 | — |
| timestamp | {"date": 836} | 231 | `{}` | 0 | 2018-01-01 … 2022-10-31 |

### Значения: все при ≤60 уникальных, иначе 20 самых частых

**ISIN**

```json
{
  "GRS498003003": 3,
  "GRC8161185B1": 3,
  "LU0055631609": 2,
  "GRS504003021": 2,
  "GRC1441197B3": 2,
  "GRC1451184D4": 2,
  "GRC2451227D9": 2,
  "GRC281121BD8": 2,
  "GRC419120AD7": 2,
  "GRC4261213D5": 2,
  "GRC4951193D4": 2,
  "GRC4971221B3": 2,
  "GRC5091217D9": 2,
  "GRC5211214B5": 2,
  "GRC813119AD1": 2,
  "GRC8171186B7": 2,
  "GRC8231227D3": 2,
  "GRS520003005": 2,
  "GRS525003000": 2,
  "ES0173516115": 2
}
```

**assetName**

```json
{
  "": 24,
  "European Investment Bank (EIB)": 21,
  "Italy": 7,
  "Apple": 6,
  "Spain": 4,
  "USA": 4,
  "Cyprus": 4,
  "Petrobras": 4,
  "Portugal": 3,
  "EPSILON NET S.A. (CR)": 3,
  "Costamare Inc": 3,
  "CORAL A.E. OIL AND CHEMICALS COMPANY": 3,
  "Germany": 3,
  "Telecom Italia (TIM)": 3,
  "France": 2,
  "BlackRock Global Funds - World Gold Fund A2": 2,
  "ALPHA TRUST MUTUAL FUND AND ALTERNATIVE INVESTMENT": 2,
  "AT&T Inc": 2,
  "ATTICA HOLDINGS S.A.": 2,
  "GEK TERNA HOLDING, REAL ESTATE, CONSTRUCTION S.A.": 2
}
```

**assetShortName**

```json
{
  "ΕΠΣΙΛ": 3,
  "ΚΟΡΑΛΟ1": 3,
  "GOLD": 2,
  "ΑΤΡΑΣΤ": 2,
  "ΑΤΤΙΚΑΟ1": 2,
  "ΓΕΚΤΕΡΝΑΟ1": 2,
  "ΛΑΜΔΑΟ2": 2,
  "ΕΛΧΑΟ1": 2,
  "ΟΠΑΠΟ2": 2,
  "ΜΟΗΟ1": 2,
  "ΑΡΑΙΓΟ1": 2,
  "ΠΡΕΜΙΑΟ1": 2,
  "ΠΡΟΝΤΕΑΟ1": 2,
  "CMPB1": 2,
  "ΤΕΝΕΡΓΧΟ2": 2,
  "ΒΚΑΙΦΟ1": 2,
  "CPLPB2": 2,
  "ΜΟΥΖΚ": 2,
  "ΙΝΤΚΑ": 2,
  "ΛΕΒΚ": 2
}
```

**assetCategory**

```json
{
  "MTF": 318,
  "Stock": 293,
  "Bond": 225
}
```

**assetSubCategory**

```json
{
  "Balanced": 8,
  "Structured": 2,
  "Money Market": 19,
  "Bond": 108,
  "Equity": 107,
  "": 269,
  "Government": 55,
  "Other": 73,
  "Corporate": 170,
  "Large Cap": 24,
  "Bonds": 1
}
```

**marketID**

```json
{
  "AEDAK": 18,
  "ALXA": 2,
  "ALXB": 2,
  "ALXP": 10,
  "CCLX": 71,
  "ENAX": 20,
  "ENXL": 1,
  "HDAT": 11,
  "MTAA": 10,
  "PORT": 1,
  "OOTC": 4,
  "XAMS": 2,
  "XASM": 2,
  "XASX": 2,
  "XATH": 214,
  "XBAR": 6,
  "XBER": 12,
  "XCIE": 2,
  "XCYS": 2,
  "XDUB": 9,
  "XETR": 81,
  "XHEL": 2,
  "XHKG": 1,
  "XLON": 40,
  "XLUX": 149,
  "XMAD": 4,
  "XMOD": 2,
  "XMUN": 9,
  "XNAS": 1,
  "XNEC": 2,
  "XNGS": 6,
  "XNMS": 1,
  "XNYS": 89,
  "XOSL": 2,
  "XPAR": 18,
  "XSTU": 10,
  "XSWX": 1,
  "EBB": 17
}
```

**sector**

```json
{
  "": 388,
  "Technology": 30,
  "Industrials": 44,
  "Consumer Defensive": 18,
  "Consumer Cyclical": 41,
  "Financial Services": 26,
  "Communication Services": 13,
  "Sovereign": 49,
  "Sector Equity Precious Metals": 1,
  "Corporate": 165,
  "Healthcare": 12,
  "Basic Materials": 19,
  "Real Estate": 12,
  "Energy": 10,
  "Utilities": 7,
  "EUR High Yield Bond": 1
}
```

**industry**

```json
{
  "": 439,
  "Banks": 55,
  "Oil and Gas Extraction and Refining": 16,
  "Textile Manufacturing": 11,
  "Software - Application": 10,
  "Marine Shipping": 10,
  "Engineering & Construction": 10,
  "Asset Management": 8,
  "Power": 8,
  "Packaged Foods": 8,
  "IT equipment": 8,
  "Banks - Regional": 7,
  "Steel": 7,
  "Oil & Gas Integrated": 7,
  "Food and Beverage Production": 7,
  "Telecom Services": 6,
  "Communication Services": 6,
  "Marine Transportation": 6,
  "Auto Manufacturers": 5,
  "Miscellaneous Construction": 5
}
```

**timestamp**

```json
{
  "2018-01-02": 474,
  "2018-11-16": 52,
  "2018-01-03": 15,
  "2018-01-01": 10,
  "2018-11-19": 8,
  "2020-07-22": 4,
  "2021-06-09": 4,
  "2022-10-31": 3,
  "2018-02-02": 3,
  "2018-09-28": 3,
  "2020-01-16": 3,
  "2020-02-03": 2,
  "2021-08-12": 2,
  "2019-04-12": 2,
  "2021-03-17": 2,
  "2022-03-30": 2,
  "2018-04-30": 2,
  "2018-01-31": 2,
  "2019-12-09": 2,
  "2019-03-13": 2
}
```

## close_prices.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/close_prices.csv`; SHA-256: `6ba1fe8390b31dfb3ab4e3e824910f9e8da4684cb6074cdb82eb6422a323656d`.

Строк: **703,303**; полных дубликатов: 0; некорректных CSV-записей: 0.

| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |
|---|---|---:|---|---:|---|
| ISIN | {"identifier_string": 703303} | 807 | `{}` | 0 | — |
| timestamp | {"date": 703303} | 1279 | `{}` | 0 | 2018-01-01 … 2022-11-29 |
| closePrice | {"decimal": 703303} | 347772 | `{}` | 0 | 0.01 … 3783.5 |

### Значения: все при ≤60 уникальных, иначе 20 самых частых

**ISIN**

```json
{
  "ES0000012A89": 1279,
  "IE00B4S3JD47": 1279,
  "XS0210976329": 1279,
  "NO0010757925": 1279,
  "100974271034": 1278,
  "BE0974271034": 1278,
  "BE0974293251": 1278,
  "BE0974303357": 1278,
  "CH0198251305": 1278,
  "DE0002635307": 1278,
  "DE0005552004": 1278,
  "DE0005557508": 1278,
  "DE0005933931": 1278,
  "DE0005933956": 1278,
  "DE0006047004": 1278,
  "DE0006599905": 1278,
  "DE0007100000": 1278,
  "DE0007164600": 1278,
  "DE0008404005": 1278,
  "DE000A0H0728": 1278
}
```

**timestamp**

```json
{
  "2019-04-12": 603,
  "2019-05-07": 603,
  "2019-05-20": 603,
  "2019-05-21": 603,
  "2019-04-15": 602,
  "2019-04-16": 602,
  "2019-04-17": 602,
  "2019-04-18": 602,
  "2019-04-24": 602,
  "2019-04-25": 602,
  "2019-04-26": 602,
  "2019-05-02": 602,
  "2019-05-03": 602,
  "2019-05-06": 602,
  "2019-05-22": 602,
  "2019-05-23": 602,
  "2019-05-31": 602,
  "2019-06-03": 602,
  "2019-06-04": 602,
  "2019-06-05": 602
}
```

**closePrice**

```json
{
  "4.8": 1474,
  "0.11": 1227,
  "100.0": 1160,
  "2.6": 1124,
  "0.57": 1057,
  "0.072": 1026,
  "0.14": 967,
  "0.448": 939,
  "0.0125": 861,
  "0.9": 837,
  "0.3": 824,
  "0.5": 803,
  "0.1": 756,
  "0.2": 742,
  "65.0": 691,
  "0.035": 680,
  "74.0": 678,
  "89.9": 674,
  "3.96": 669,
  "0.28": 656
}
```

## customer_information.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/customer_information.csv`; SHA-256: `c4ad52ebca90e32bf3df5eb64f362b7a3437b77d978b22627cc46927fe7064af`.

Строк: **32,468**; полных дубликатов: 0; некорректных CSV-записей: 0.

| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |
|---|---|---:|---|---:|---|
| customerID | {"identifier_string": 32468} | 29090 | `{}` | 0 | — |
| customerType | {"string": 32468} | 5 | `{}` | 0 | — |
| riskLevel | {"string": 32124, "missing_marker": 344} | 9 | `{"Not_Available": 344}` | 7274 | — |
| investmentCapacity | {"string": 32121, "missing_marker": 347} | 9 | `{"Not_Available": 347}` | 7454 | — |
| lastQuestionnaireDate | {"date": 32468} | 1555 | `{}` | 0 | 2000-01-01 … 2022-11-23 |
| timestamp | {"date": 32468} | 1167 | `{}` | 0 | 2000-01-01 … 2022-11-30 |

### Значения: все при ≤60 уникальных, иначе 20 самых частых

**customerID**

```json
{
  "26FE717B0D0ABFEF14B9": 9,
  "ABEB93D64BBCFEE55B29": 7,
  "8973886ABB3FDED452BB": 7,
  "E3854B8B91DA47B7FC08": 7,
  "FED2F4303CEAA23D86CB": 7,
  "171D0AB1AD7F053627F4": 7,
  "3D2A12FE315EA4CB0C55": 7,
  "42DD1D76D74555926931": 7,
  "2276103D3FB4708CB10F": 7,
  "12AEFC59F28D1B84CB5B": 7,
  "F533D4CEA3B3F5D0CAB5": 6,
  "4C98E064B04EDD085D03": 6,
  "882FD584432B55DA325F": 6,
  "7DC65E98E2F8078E6393": 6,
  "88131369A9C617CDAE90": 6,
  "3ACA1FF11A0E4D3BB16B": 6,
  "6F83971884D5E61371BC": 6,
  "B7E79BAB00123CFAE2E2": 6,
  "BD07AEA1BF04BB7B7C0F": 6,
  "628E2E51B98A748DF469": 6
}
```

**customerType**

```json
{
  "Premium": 10321,
  "Mass": 19810,
  "Professional": 2046,
  "Inactive": 211,
  "Legal Entity": 80
}
```

**riskLevel**

```json
{
  "Balanced": 8684,
  "Income": 10048,
  "Predicted_Conservative": 2842,
  "Conservative": 2916,
  "Predicted_Balanced": 1430,
  "Aggressive": 3202,
  "Predicted_Income": 2704,
  "Predicted_Aggressive": 298,
  "Not_Available": 344
}
```

**investmentCapacity**

```json
{
  "CAP_80K_300K": 4220,
  "Predicted_CAP_LT30K": 5449,
  "CAP_30K_80K": 5529,
  "CAP_LT30K": 14030,
  "Predicted_CAP_80K_300K": 1025,
  "Predicted_CAP_30K_80K": 965,
  "CAP_GT300K": 888,
  "Predicted_CAP_GT300K": 15,
  "Not_Available": 347
}
```

**lastQuestionnaireDate**

```json
{
  "2000-01-01": 7275,
  "2018-01-02": 308,
  "2021-07-16": 224,
  "2021-03-18": 204,
  "2021-03-19": 187,
  "2021-03-17": 179,
  "2020-06-29": 179,
  "2021-07-14": 179,
  "2021-11-04": 166,
  "2021-07-15": 166,
  "2020-06-30": 164,
  "2021-11-03": 150,
  "2020-07-01": 134,
  "2018-03-29": 109,
  "2022-01-19": 107,
  "2021-11-02": 105,
  "2022-01-20": 103,
  "2022-01-21": 99,
  "2018-01-04": 96,
  "2018-01-03": 93
}
```

**timestamp**

```json
{
  "2018-01-02": 15752,
  "2021-03-19": 1422,
  "2021-07-16": 964,
  "2022-01-21": 451,
  "2021-11-12": 391,
  "2020-10-23": 223,
  "2022-07-08": 203,
  "2000-01-01": 130,
  "2018-09-14": 113,
  "2020-03-09": 99,
  "2018-03-27": 84,
  "2020-03-16": 75,
  "2020-02-28": 73,
  "2020-02-24": 73,
  "2020-03-17": 66,
  "2020-03-03": 65,
  "2021-05-21": 64,
  "2021-08-12": 64,
  "2020-02-19": 63,
  "2020-03-12": 61
}
```

## limit_prices.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/limit_prices.csv`; SHA-256: `b5a9bc304e2a4a31f5e3d0959b22c5c6135b69f13ce6f92123fc7e1e92600c8f`.

Строк: **807**; полных дубликатов: 0; некорректных CSV-записей: 0.

| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |
|---|---|---:|---|---:|---|
| ISIN | {"identifier_string": 807} | 807 | `{}` | 0 | — |
| minDate | {"date": 807} | 211 | `{}` | 0 | 2018-01-01 … 2022-10-31 |
| maxDate | {"date": 807} | 211 | `{}` | 0 | 2018-01-19 … 2022-11-29 |
| priceMinDate | {"decimal": 807} | 765 | `{}` | 0 | 0.0145 … 3409.45 |
| priceMaxDate | {"decimal": 807} | 775 | `{}` | 0 | 0.0125 … 3344.561658 |
| profitability | {"decimal": 807} | 798 | `{}` | 0 | -0.997241213865899 … 83.54545454545456 |

### Значения: все при ≤60 уникальных, иначе 20 самых частых

**ISIN**

```json
{
  "100974271034": 1,
  "BE0974271034": 1,
  "BE0974293251": 1,
  "BE0974303357": 1,
  "CH0106027144": 1,
  "CH0198251305": 1,
  "CY0109232112": 1,
  "CY0109561015": 1,
  "CY0109610614": 1,
  "CY0200222111": 1,
  "CY0200252118": 1,
  "DE0001102325": 1,
  "DE0001102457": 1,
  "DE0001135275": 1,
  "DE0001141703": 1,
  "DE0002635307": 1,
  "DE0005552004": 1,
  "DE0005557508": 1,
  "DE0005933931": 1,
  "DE0005933949": 1
}
```

**minDate**

```json
{
  "2018-01-02": 472,
  "2018-11-16": 52,
  "2018-01-03": 15,
  "2018-01-01": 10,
  "2018-11-19": 8,
  "2021-06-09": 4,
  "2022-10-31": 3,
  "2020-07-22": 3,
  "2018-02-02": 3,
  "2018-09-28": 3,
  "2020-01-16": 3,
  "2021-08-12": 2,
  "2019-06-12": 2,
  "2019-09-09": 2,
  "2019-04-08": 2,
  "2020-02-03": 2,
  "2021-03-17": 2,
  "2018-06-20": 2,
  "2018-09-14": 2,
  "2019-08-12": 2
}
```

**maxDate**

```json
{
  "2022-11-29": 522,
  "2019-07-10": 15,
  "2019-06-06": 7,
  "2021-12-15": 4,
  "2019-12-20": 4,
  "2020-12-17": 3,
  "2019-09-23": 3,
  "2020-03-12": 3,
  "2019-12-30": 3,
  "2020-07-13": 3,
  "2019-05-07": 3,
  "2021-03-15": 3,
  "2020-02-24": 3,
  "2021-08-11": 3,
  "2022-01-13": 2,
  "2019-09-25": 2,
  "2020-10-01": 2,
  "2021-01-15": 2,
  "2019-09-19": 2,
  "2019-08-09": 2
}
```

**priceMinDate**

```json
{
  "100.0": 25,
  "0.49": 3,
  "0.6": 3,
  "0.38": 2,
  "2.08": 2,
  "0.85": 2,
  "0.06": 2,
  "0.78": 2,
  "4.7": 2,
  "0.33": 2,
  "9.3": 2,
  "0.142": 2,
  "0.58": 2,
  "1.36": 2,
  "4.92": 2,
  "1.77": 2,
  "15.99": 2,
  "3.33": 1,
  "3.345": 1,
  "93.26": 1
}
```

**priceMaxDate**

```json
{
  "100.0": 13,
  "0.22": 3,
  "0.37": 2,
  "22.05": 2,
  "0.105": 2,
  "0.444": 2,
  "0.95": 2,
  "1.6": 2,
  "0.186": 2,
  "3.08": 2,
  "2.1": 2,
  "1.73": 2,
  "1.05": 2,
  "0.57": 2,
  "2.6": 2,
  "0.11": 2,
  "1.5": 2,
  "0.449": 2,
  "10.0": 2,
  "45.981162": 2
}
```

**profitability**

```json
{
  "0.0": 9,
  "-0.0294117647058823": 2,
  "0.2507507507507507": 1,
  "0.2376681614349774": 1,
  "-0.3973836585888913": 1,
  "1.58716323296355": 1,
  "-0.0293951384963256": 1,
  "-0.1433837080722447": 1,
  "0.1516646115906287": 1,
  "-0.0339805825242718": 1,
  "0.3214285714285713": 1,
  "0.4884004884004883": 1,
  "0.5679314565483476": 1,
  "-0.0976779255918827": 1,
  "-0.0914791523721449": 1,
  "0.1701229885666231": 1,
  "-0.0090592505877839": 1,
  "0.1417105263157894": 1,
  "-0.0427173170793393": 1,
  "0.3115922538999462": 1
}
```

## markets.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/markets.csv`; SHA-256: `009d5764b5eb59e979d8c22954482cf7bb8ed5fdb3382a6fb03f3c6cd1316960`.

Строк: **38**; полных дубликатов: 0; некорректных CSV-записей: 0.

| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |
|---|---|---:|---|---:|---|
| exchangeID | {"identifier_string": 38} | 29 | `{}` | 0 | — |
| marketID | {"identifier_string": 38} | 38 | `{}` | 0 | — |
| name | {"string": 38} | 38 | `{}` | 0 | — |
| description | {"string": 38} | 37 | `{}` | 0 | — |
| country | {"string": 37, "missing_marker": 1} | 20 | `{"-": 1}` | 0 | — |
| tradingDays | {"string": 38} | 1 | `{}` | 0 | — |
| tradingHours | {"string": 37, "missing_marker": 1} | 13 | `{"": 1}` | 0 | — |
| marketClass | {"string": 38} | 3 | `{}` | 0 | — |

### Значения: все при ≤60 уникальных, иначе 20 самых частых

**exchangeID**

```json
{
  "AEDAK": 1,
  "XAMS": 2,
  "XBRU": 1,
  "XPAR": 2,
  "XLUX": 2,
  "ATHEX": 3,
  "XLIS": 1,
  "HDAT": 1,
  "MTAA": 1,
  "OOTC": 1,
  "XMTS": 1,
  "XDUB": 2,
  "XASX": 1,
  "BMEX": 2,
  "XBER": 1,
  "XCIE": 1,
  "XCYS": 1,
  "XETR": 1,
  "XHEL": 1,
  "XHKG": 1,
  "XLON": 1,
  "XMOD": 1,
  "XMUN": 1,
  "XNAS": 3,
  "XNEC": 1,
  "XNYS": 1,
  "XOSL": 1,
  "XSTU": 1,
  "XSWX": 1
}
```

**marketID**

```json
{
  "AEDAK": 1,
  "ALXA": 1,
  "ALXB": 1,
  "ALXP": 1,
  "CCLX": 1,
  "ENAX": 1,
  "ENXL": 1,
  "HDAT": 1,
  "MTAA": 1,
  "OOTC": 1,
  "PORT": 1,
  "XAMS": 1,
  "XASM": 1,
  "XASX": 1,
  "XATH": 1,
  "XBAR": 1,
  "XBER": 1,
  "XCIE": 1,
  "XCYS": 1,
  "XDUB": 1,
  "XETR": 1,
  "XHEL": 1,
  "XHKG": 1,
  "XLON": 1,
  "XLUX": 1,
  "XMAD": 1,
  "XMOD": 1,
  "XMUN": 1,
  "XNAS": 1,
  "XNEC": 1,
  "XNGS": 1,
  "XNMS": 1,
  "XNYS": 1,
  "XOSL": 1,
  "XPAR": 1,
  "XSTU": 1,
  "XSWX": 1,
  "EBB": 1
}
```

**name**

```json
{
  "AEDAK Funds": 1,
  "Euronext - Growth Amsterdam": 1,
  "Euronext - Growth Brussels": 1,
  "Euronext - Growth Paris": 1,
  "Finesti S.A.": 1,
  "Athens Stock Exchange Alternative Market": 1,
  "Euronext Access Lisbon": 1,
  "Electronic Secondary Securities Market": 1,
  "Borsa Italiana": 1,
  "Other OTC": 1,
  "MTS Portugal": 1,
  "Euronext - Euronext Amsterdam": 1,
  "Irish Stock Exchange Global Exchange Market": 1,
  "Australia Securities Exchange All Markets": 1,
  "Athens Exchange S.A. Cash Market": 1,
  "Borsa de Barcelona": 1,
  "Boerse Berlin": 1,
  "The International Stock Exchange": 1,
  "Cyprus Stock Exchange": 1,
  "Irish Stock Exchange All Markets": 1,
  "Xetra": 1,
  "NASDAQ Helsinki Limited": 1,
  "Hong Kong Exchanges and Clearing Ltd": 1,
  "London Stock Exchange": 1,
  "Luxembourg Stock Exchange": 1,
  "Bolsa de Madrid": 1,
  "The Montreal Exchange / Bourse de Montreal": 1,
  "Boerse Muenchen": 1,
  "NASDAQ All Markets": 1,
  "National Stock Exchange of Australia Limited": 1,
  "NASDAQ/NGS (Global Select Market)": 1,
  "NASDAQ/NMS (Global Market)": 1,
  "New York Stock Exchange": 1,
  "Oslo Bors": 1,
  "Euronext - Euronext Paris": 1,
  "Boerse Stuttgart": 1,
  "SIX Swiss Exchange": 1,
  "Electronic Book Building Athex": 1
}
```

**description**

```json
{
  "Mutual funds offered by EFG Eurobank and Deutsche Bank": 1,
  "The Euronext is a pan-European bourse providing trading services. This is the Euronext Growth market operating in Amsterdam, Netherlands. Euronext Growth is suited to small and mid sized companies (SMEs).  Investors can trade here stocks, bonds, stock options, index options and index futures.": 1,
  "The Euronext is a pan-European bourse providing trading services. This is the Euronext Growth market operating in Brussels. Euronext Growth is suited to small and mid sized companies (SMEs). Investors can trade here stocks, bonds and index funds.": 1,
  "The Euronext is a pan-European bourse providing trading services. This is the Euronext Growth market operating in Paris, France. Euronext Growth is suited to small and mid sized companies (SMEs).  Investors can trade here stocks, bonds, ETFs, options, futures, commodities, warrants and other securities": 1,
  "Finesti is a Luxembourg-based company for managing of data related to investment funds. It was founded in 1995 and it is part of the Luxembourg Stock Exchange.": 1,
  "The Athens Stock Exchange (ASE or ATHEX) is the stock exchange of Greece, based in the capital city of Athens. It was founded in 1876. This is a secondary market, addressed to SMEs and early-stage business development companies.": 1,
  "The Euronext is a pan-European bourse providing trading services. This is the Euronext Access market operating in Lisbon, Portugal. Euronext Growth is suited to start-ups and SMEs.  Investors can trade here stocks, bonds, ETFs and warrants.": 1,
  "The Electronic Secondary Securities Market (HDAT) is  a secondary market operated by the Bank of Greece. It was founded in 1999. Investors can trade Greek governement securities, bonds, fixed-income debt securities.": 1,
  "Borsa Italiana is the Italian Stock Exchange, based in Milan. It is expected to be rebranded as Euronext Milan. It was founded in 1808. Investors can trade stocks, ETPs, funds, derivatives and bonds.": 1,
  "Securities in this market are sold by their owner. These are stocks, bonds and other financial securities which are traded directly between two parties, instead of on a public stock market.": 1,
  "MTS Portugal was a regulated market for trading of Portuguese government securities. MTS is no longer trading since the end of 2019.": 1,
  "The Euronext is a pan-European bourse providing trading services. This is the Euronext market operating in Amsterdam, Netherlands. Investors can trade here stocks, bonds, stock options, index options and index futures.": 1,
  "The Irish Stock Exchange (also known as Euronext Dublin) is Ireland's main stock exchange, based in Dublin. It was founded in 1793. Investors can trade stocks, bonds, Irish government onds, funds and ETFs.": 2,
  "The Australian Securities Exchange is the primary securities exchange in Australia. Investors can trade equities, fixed income, commodities and energy.": 1,
  "The Athens Stock Exchange (ASE or ATHEX) is the stock exchange of Greece, based in the capital city of Athens. It was founded in 1876. This is the main trading market, known as the regulated securities market. Here investors can trade in stocks, bonds, ETFs and other related securities.": 1,
  "Borsa de Barcelona is a Spanish stock exchange, based in Barcelona. It was founded in 1915. It is exclusively dedicated to the trade of shares and convertible values. ": 1,
  "The Boerse Berlin (or Berlin Stock Exchange) is a stock exchange based in Berlin, Germany. It was founded in 1685. Investors can trade stocks and bonds.": 1,
  "The Internationa Stock Exchange (TISE) is a stock exchange based in St. Peter Port, Guernsey. It was founded in 2013. Investors can trade equities and bonds": 1,
  "The Cyprus Stock Exchange (CSE) is the stock exchange of Cyprus, based in Nicosia. It was founded in 1996. Investors can trade shares and bonds.": 1,
  "Xetra is a trading venue operated by the Frankfurt Stock Exchange. It is the reference market for German equities and ETFs.": 1,
  "NASDAQ Helsinki is a stock exchange located in Helsinki, Finland. It was founded in 1912. Investors can trade stocks.": 1,
  "Hong Kong Exchanges and Clearing Limited  operates a range of equity, commoditiy, fixed income and currency markets. It was founded in 2000.": 1,
  "The London Stock Exchange (LSE) is a stock exchange based in the City of London, England. It was founded in 1801 and it is the most-valued stock exchange in Europe. Investors can trade stocks, bonds and ETFs.": 1,
  "The Luxembourg Stock Exchange is a stock exchange based in Luxembourgh City. It was founded in 1928. It primarily specializes in the listing of international bonds.": 1,
  "Bolsa de Madrid is the largest and most international of Spanish stock exchanges. It was founded in 1831. Investors can trade shares, convertible bonds and fixed income securities, as well as both government and private-sector debt. It is owned by Bolsas y Mercados Espanoles (BME)": 1,
  "The Montreal Exchange is a derivatives exchange located in Montreal, Canada. It was founded in 1965. Investors can trade futures contracts and options on equities, indices, currencies, ETFs, energy and interest rates.": 1,
  "The Börse München is a stock exchange based in Munich, Germany. It was founded in 1830. In this market, investors can trade in stocks, bonds, funds, ETFs and derivatives.": 1,
  "NASDAQ (National Association of Securities Dealears Automated Quotations) is an American stock exchange based in New York. It is the most active stock trading venue in the USA by volume. It was founded in 1971. Investors can trade stocks, options, ETfs, mutual funds, commodities, cryptocurrencies or futures, among other securities.": 1,
  "The National Stock Exchange of Australia is a stock exchange based in Sidney. It was founded in 1937. Investors can exchange equities, debt and managed investment schemes.": 1,
  "NASDAQ (National Association of Securities Dealears Automated Quotations) is an American stock exchange based in New York. It is the most active stock trading venue in the USA by volume. It was founded in 1971. This market is the Global Select Market,which has the highest initial listing standards. Investors can trade stocks, options, ETfs, mutual funds, commodities, cryptocurrencies or futures, among other securities.": 1,
  "NASDAQ (National Association of Securities Dealears Automated Quotations) is an American stock exchange based in New York. It is the most active stock trading venue in the USA by volume. It was founded in 1971. This market is the Global Market,the second U.S. market tier, listing companies with global leadership and international reach. Investors can trade stocks, options, ETfs, mutual funds, commodities, cryptocurrencies or futures, among other securities.": 1,
  "The New York Stock Exchange (NYSE) is an American stock exchange. It was founded in 1792 and it is the largest stock exchange worldwide. Investors can trade stocks, bonds, options and ETPs.": 1,
  "The Oslo Bors (or Oslo Stock Exchange) is the only regulated market in Norway, based in Oslo. It was founded in 1819. Investors can trade equities, derivatives and fixed income instruments.": 1,
  "The Euronext is a pan-European bourse providing trading services. This is the Euronext market operating in Paris, France. Investors can trade here stocks, bonds, ETFs, options, futures, commodities, warrants and other securities": 1,
  "Boerse Stuttgart (SWB) is the second largest stock exchange in Germany, based in Stuttgart. It was founded in 1860. Investors can trade stocks, bonds, warrants, ETPs, funds, etc.": 1,
  "The SIX Swiss Exchange is Switzerland's principal stock exchange. It was founded in its current form in 1993. Investors can trade stocks, Swiss government bonds and derivatives.": 1,
  "The EBB (Electronic Book Building)  is a service offered by ATHEX to support fund-raising process through ATHEX. It is a mechanism provided centrally in the trading order routing system, in an attempt to use the network of ATHEX members and their clients.": 1
}
```

**country**

```json
{
  "Greece": 5,
  "Netherlands": 2,
  "Belgium": 1,
  "France": 2,
  "Luxembourg": 2,
  "Portugal": 2,
  "Italy": 1,
  "-": 1,
  "Ireland": 2,
  "Australia": 2,
  "Spain": 2,
  "Germany": 4,
  "United Kingdom": 2,
  "Cyprus": 1,
  "Finland": 1,
  "China": 1,
  "Canada": 1,
  "USA": 4,
  "Norway": 1,
  "Switzerland": 1
}
```

**tradingDays**

```json
{
  "Mon,Tue,Wed,Thu,Fri": 38
}
```

**tradingHours**

```json
{
  "08:15-15:20": 5,
  "08:00-16:30": 15,
  "": 1,
  "00:00-06:00": 2,
  "07:00-21:00": 4,
  "09:00-16:30": 1,
  "08:30-15:00": 1,
  "08:00-16:00": 1,
  "02:30-09:30": 1,
  "07:00-15:30": 1,
  "07:00-21:30": 1,
  "14:30-21:00": 4,
  "08:00-15:20": 1
}
```

**marketClass**

```json
{
  "Public Securities": 36,
  "Private Securities": 1,
  "EFG Eurobank Mutual Funds": 1
}
```

## questionnaires.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/questionnaires.csv`; SHA-256: `f4a902f7ac344f70708433a40d33163972da1652d6f91a42e3e280b17eedcea0`.

Текст, 177 строк. Не таблица наблюдений.

## README.txt

Путь: `data/raw/FAR-Trans/FAR-Trans/README.txt`; SHA-256: `5aa20b492c9fe18c8b5a147ad13fae99862c78aea59cbf542b734b5eef9ea072`.

Текст, 162 строк. Не таблица наблюдений.

## transactions.csv

Путь: `data/raw/FAR-Trans/FAR-Trans/transactions.csv`; SHA-256: `358871fa1311a802799df86e56c3d633513566965b01412d058e0f8fbe6cd54b`.

Строк: **388,048**; полных дубликатов: 0; некорректных CSV-записей: 0.

| Поле | Типы (число строк) | Уникальных | Пропуски | Predicted_ | Диапазон |
|---|---|---:|---|---:|---|
| customerID | {"identifier_string": 388048} | 29090 | `{}` | 0 | — |
| ISIN | {"identifier_string": 388048} | 320 | `{}` | 0 | — |
| transactionID | {"identifier_string": 388048} | 359128 | `{}` | 0 | — |
| transactionType | {"string": 388048} | 2 | `{}` | 0 | — |
| timestamp | {"date": 388048} | 1232 | `{}` | 0 | 2018-01-02 … 2022-11-30 |
| totalValue | {"decimal": 388048} | 105122 | `{}` | 0 | 2.831068712794149e-16 … 27159117.913728 |
| units | {"decimal": 388048} | 23998 | `{}` | 0 | 5.898059818321144e-17 … 2150000.0 |
| channel | {"string": 388048} | 3 | `{}` | 0 | — |
| marketID | {"identifier_string": 388048} | 16 | `{}` | 0 | — |

### Значения: все при ≤60 уникальных, иначе 20 самых частых

**customerID**

```json
{
  "DD35198E5AFDB753ED0D": 6288,
  "DD1E7FA6C74787F13EC7": 3228,
  "B44585A3FAB09C5B4511": 2555,
  "E6D47D738DE7C89E3C20": 2539,
  "CB8A0D4D71F631B2396B": 2217,
  "AFA70DC9566646F0D9D5": 1565,
  "3B5EED51E19461C1FAFE": 1499,
  "814C9F95DD9ED81CAF29": 1486,
  "7EC41C0A4526D707FB88": 1434,
  "5670A215A1EF39E196CD": 1411,
  "A77DFF56D3A2D0E21E22": 1349,
  "A3475AFF8E18AE9B6DDE": 1291,
  "D459BFD78925AEC6256F": 1210,
  "E3AEE99C06246895F54C": 1206,
  "535266109F7417B87AD6": 1199,
  "90BF28B439D48D60C1F4": 1183,
  "AC5BCAF7299C672160AF": 1181,
  "49686690383E474AD41A": 1111,
  "C533A31465D27CA3E293": 1076,
  "D2C337549295AA89DE09": 1064
}
```

**ISIN**

```json
{
  "GRS003003035": 44783,
  "GRS015003007": 33222,
  "GRS014003032": 22999,
  "GRS323003012": 19099,
  "GRS434003000": 16970,
  "GRS393503008": 12447,
  "GRS419003009": 11894,
  "GRS260333000": 11390,
  "GRS426003000": 7717,
  "GRS298343005": 7635,
  "GRF000037009": 7204,
  "GRS191213008": 7080,
  "GRS314003005": 6281,
  "GRS518003009": 6059,
  "GRS001003037": 5662,
  "GRS495003006": 5591,
  "GRS087003000": 5070,
  "GRS395363005": 4587,
  "GRF000038007": 4478,
  "GRS496003005": 3985
}
```

**transactionID**

```json
{
  "9796569": 5,
  "10412111": 5,
  "8785195": 5,
  "9862488": 5,
  "7630397": 5,
  "7657512": 5,
  "7668610": 5,
  "10288844": 5,
  "11623358": 5,
  "11628278": 5,
  "8889031": 5,
  "7863167": 5,
  "8032048": 5,
  "8652899": 5,
  "8730838": 5,
  "8762158": 5,
  "8768058": 5,
  "8889032": 5,
  "10179526": 5,
  "7561869": 5
}
```

**transactionType**

```json
{
  "Buy": 228913,
  "Sell": 159135
}
```

**timestamp**

```json
{
  "2018-01-02": 35739,
  "2021-03-19": 3022,
  "2021-07-16": 2719,
  "2021-11-12": 1899,
  "2022-01-21": 1803,
  "2020-03-09": 1533,
  "2022-02-24": 1532,
  "2020-02-24": 1531,
  "2021-05-21": 1484,
  "2020-02-28": 1422,
  "2020-03-16": 1232,
  "2021-04-14": 1198,
  "2022-03-08": 1139,
  "2020-03-12": 1094,
  "2020-03-06": 1045,
  "2020-03-17": 1019,
  "2020-03-20": 1010,
  "2020-12-21": 996,
  "2022-03-02": 987,
  "2022-02-14": 960
}
```

**totalValue**

```json
{
  "200.0": 1192,
  "300.0": 991,
  "400.0": 973,
  "100.0": 921,
  "800.0": 893,
  "700.0": 871,
  "500.0": 756,
  "1500.0": 683,
  "1100.0": 668,
  "600.0": 668,
  "1000.0": 627,
  "3.24": 616,
  "900.0": 608,
  "2200.0": 555,
  "1200.0": 507,
  "416.0": 504,
  "1300.0": 487,
  "1400.0": 447,
  "2000.0": 422,
  "3000.0": 410
}
```

**units**

```json
{
  "1000.0": 33363,
  "500.0": 21127,
  "100.0": 19619,
  "2000.0": 15675,
  "200.0": 15283,
  "300.0": 9998,
  "5000.0": 8680,
  "50.0": 8410,
  "3000.0": 8184,
  "10000.0": 7357,
  "400.0": 5961,
  "1500.0": 5641,
  "150.0": 4955,
  "10.0": 4559,
  "250.0": 4480,
  "20.0": 4296,
  "4000.0": 4255,
  "600.0": 3410,
  "1.0": 3344,
  "30.0": 3342
}
```

**channel**

```json
{
  "Internet Banking": 250805,
  "Phone Banking": 65977,
  "Branch": 71266
}
```

**marketID**

```json
{
  "XATH": 341211,
  "ENAX": 7265,
  "AEDAK": 27954,
  "EBB": 9498,
  "XLUX": 828,
  "CCLX": 768,
  "ALXB": 152,
  "HDAT": 314,
  "XETR": 22,
  "XDUB": 4,
  "XSTU": 4,
  "XBER": 8,
  "XCYS": 11,
  "XNYS": 4,
  "XCIE": 3,
  "XLON": 2
}
```

## Межфайловые проверки и точный пример

```json
{
  "transactions_unknown_customer": [],
  "transactions_unknown_asset": [],
  "prices_without_asset_metadata": [
    "GRX497003012"
  ],
  "assets_without_prices": [],
  "transaction_unknown_market": [],
  "asset_unknown_market": [],
  "customer_questionnaire_after_timestamp": 12501,
  "customer_questionnaire_sentinel_2000": 7275,
  "customer_timestamp_sentinel_2000": 130,
  "customer_questionnaire_after_timestamp_example": {
    "customerID": "DED5BF19E23CCCFEE322",
    "customerType": "Premium",
    "riskLevel": "Balanced",
    "investmentCapacity": "CAP_80K_300K",
    "lastQuestionnaireDate": "2021-11-30",
    "timestamp": "2021-03-19"
  },
  "customer_date_duplicate_key_groups": 0,
  "customer_date_excess_rows": 0,
  "asset_date_duplicate_key_groups": 3,
  "asset_date_excess_rows": 3,
  "asset_market_date_duplicate_key_groups": 3,
  "asset_market_date_excess_rows": 3,
  "price_date_duplicate_key_groups": 0,
  "price_date_excess_rows": 0,
  "transaction_id_duplicate_key_groups": 23388,
  "transaction_id_excess_rows": 28920,
  "negative_transaction_ids": {
    "rows": 38019,
    "types": {
      "Buy": 38019
    },
    "date_min": "2018-01-02",
    "date_max": "2022-10-31",
    "at_asset_min_date": 38019,
    "at_asset_max_date": 0,
    "first_row": {
      "customerID": "0004718496C71D464F57",
      "ISIN": "GRS434003000",
      "transactionID": "-6464",
      "transactionType": "Buy",
      "timestamp": "2018-01-02",
      "totalValue": "1524.64",
      "units": "733.0",
      "channel": "Phone Banking",
      "marketID": "XATH"
    },
    "interpretation": "Synthetic-row indicator inferred from IDs and endpoints; not an explicit provenance flag in README."
  },
  "transactions_without_same_day_price": {
    "count": 327,
    "examples": [
      {
        "csv_record_line": 16963,
        "customerID": "ABEB93D64BBCFEE55B29",
        "ISIN": "GRS434003000",
        "transactionID": "11868198",
        "transactionType": "Sell",
        "timestamp": "2022-11-30",
        "totalValue": "8016.0",
        "units": "1200.0",
        "channel": "Internet Banking",
        "marketID": "XATH"
      },
      {
        "csv_record_line": 16964,
        "customerID": "C36CC03CD6633FBB8FB9",
        "ISIN": "GRS434003000",
        "transactionID": "11868194",
        "transactionType": "Sell",
        "timestamp": "2022-11-30",
        "totalValue": "6680.0",
        "units": "1000.0",
        "channel": "Internet Banking",
        "marketID": "XATH"
      },
      {
        "csv_record_line": 16965,
        "customerID": "95ED76791B7753EA8DC1",
        "ISIN": "GRS434003000",
        "transactionID": "11867858",
        "transactionType": "Buy",
        "timestamp": "2022-11-30",
        "totalValue": "6680.0",
        "units": "1000.0",
        "channel": "Internet Banking",
        "marketID": "XATH"
      },
      {
        "csv_record_line": 16966,
        "customerID": "0E8C593A6A1B1C42EA1C",
        "ISIN": "GRS434003000",
        "transactionID": "11868207",
        "transactionType": "Sell",
        "timestamp": "2022-11-30",
        "totalValue": "3340.0",
        "units": "500.0",
        "channel": "Phone Banking",
        "marketID": "XATH"
      },
      {
        "csv_record_line": 16967,
        "customerID": "E3CF99D77968D29CA4E7",
        "ISIN": "GRS434003000",
        "transactionID": "11868212",
        "transactionType": "Sell",
        "timestamp": "2022-11-30",
        "totalValue": "728.12",
        "units": "109.0",
        "channel": "Internet Banking",
        "marketID": "XATH"
      }
    ],
    "dates": {
      "2022-11-30": 327
    },
    "types": {
      "Sell": 136,
      "Buy": 191
    }
  },
  "totalValue_not_units_times_close": {
    "count": 0,
    "examples": [],
    "relative_tolerance": 1e-08,
    "absolute_tolerance": 1e-06
  },
  "nonpositive_numeric_values": {
    "units": 0,
    "totalValue": 0,
    "closePrice": 0
  },
  "transactions_month_type": {
    "2018-01/Buy": 37474,
    "2018-01/Sell": 1898,
    "2018-02/Buy": 1283,
    "2018-02/Sell": 1261,
    "2018-03/Buy": 1372,
    "2018-03/Sell": 1060,
    "2018-04/Buy": 855,
    "2018-04/Sell": 1320,
    "2018-05/Buy": 1670,
    "2018-05/Sell": 1226,
    "2018-06/Buy": 862,
    "2018-06/Sell": 983,
    "2018-07/Buy": 623,
    "2018-07/Sell": 870,
    "2018-08/Buy": 870,
    "2018-08/Sell": 807,
    "2018-09/Buy": 1548,
    "2018-09/Sell": 909,
    "2018-10/Buy": 1204,
    "2018-10/Sell": 964,
    "2018-11/Buy": 1008,
    "2018-11/Sell": 1049,
    "2018-12/Buy": 720,
    "2018-12/Sell": 671,
    "2019-01/Buy": 567,
    "2019-01/Sell": 673,
    "2019-02/Buy": 602,
    "2019-02/Sell": 764,
    "2019-03/Buy": 822,
    "2019-03/Sell": 732,
    "2019-04/Buy": 708,
    "2019-04/Sell": 878,
    "2019-05/Buy": 952,
    "2019-05/Sell": 831,
    "2019-06/Buy": 1083,
    "2019-06/Sell": 1101,
    "2019-07/Buy": 1377,
    "2019-07/Sell": 1280,
    "2019-08/Buy": 1093,
    "2019-08/Sell": 971,
    "2019-09/Buy": 882,
    "2019-09/Sell": 901,
    "2019-10/Buy": 973,
    "2019-10/Sell": 826,
    "2019-11/Buy": 882,
    "2019-11/Sell": 755,
    "2019-12/Buy": 683,
    "2019-12/Sell": 625,
    "2020-01/Buy": 4368,
    "2020-01/Sell": 4011,
    "2020-02/Buy": 6847,
    "2020-02/Sell": 3956,
    "2020-03/Buy": 11372,
    "2020-03/Sell": 5651,
    "2020-04/Buy": 6737,
    "2020-04/Sell": 3636,
    "2020-05/Buy": 6097,
    "2020-05/Sell": 3502,
    "2020-06/Buy": 4664,
    "2020-06/Sell": 4073,
    "2020-07/Buy": 4028,
    "2020-07/Sell": 2848,
    "2020-08/Buy": 2351,
    "2020-08/Sell": 1952,
    "2020-09/Buy": 4208,
    "2020-09/Sell": 2827,
    "2020-10/Buy": 4768,
    "2020-10/Sell": 2783,
    "2020-11/Buy": 4703,
    "2020-11/Sell": 5444,
    "2020-12/Buy": 6202,
    "2020-12/Sell": 5983,
    "2021-01/Buy": 5157,
    "2021-01/Sell": 3385,
    "2021-02/Buy": 3588,
    "2021-02/Sell": 3112,
    "2021-03/Buy": 7980,
    "2021-03/Sell": 5338,
    "2021-04/Buy": 5338,
    "2021-04/Sell": 5632,
    "2021-05/Buy": 5429,
    "2021-05/Sell": 4706,
    "2021-06/Buy": 3792,
    "2021-06/Sell": 4306,
    "2021-07/Buy": 6106,
    "2021-07/Sell": 3612,
    "2021-08/Buy": 3863,
    "2021-08/Sell": 4042,
    "2021-09/Buy": 4708,
    "2021-09/Sell": 4655,
    "2021-10/Buy": 3127,
    "2021-10/Sell": 3189,
    "2021-11/Buy": 6337,
    "2021-11/Sell": 4233,
    "2021-12/Buy": 2769,
    "2021-12/Sell": 3016,
    "2022-01/Buy": 6168,
    "2022-01/Sell": 4176,
    "2022-02/Buy": 5386,
    "2022-02/Sell": 5730,
    "2022-03/Buy": 6558,
    "2022-03/Sell": 4296,
    "2022-04/Buy": 2779,
    "2022-04/Sell": 3220,
    "2022-05/Buy": 4565,
    "2022-05/Sell": 3977,
    "2022-06/Buy": 3796,
    "2022-06/Sell": 3137,
    "2022-07/Buy": 4193,
    "2022-07/Sell": 2812,
    "2022-08/Buy": 2619,
    "2022-08/Sell": 3671,
    "2022-09/Buy": 3345,
    "2022-09/Sell": 2851,
    "2022-10/Buy": 1974,
    "2022-10/Sell": 2662,
    "2022-11/Buy": 2878,
    "2022-11/Sell": 3356
  },
  "transaction_assets": 320,
  "price_assets_without_transactions": 487,
  "customers_with_at_most_3_release_rows": 16122,
  "top12_asset_transaction_share": 0.5216880385931637,
  "unique_user_asset_type": 154103,
  "unique_asset_categories": {
    "Bond": 209,
    "MTF": 315,
    "Stock": 285
  },
  "customer_rows_per_user": {
    "1": 26827,
    "2": 1560,
    "3": 437,
    "4": 162,
    "5": 74,
    "6": 20,
    "7": 9,
    "9": 1
  },
  "asset_conflicting_same_date_rows": [
    {
      "ISIN": "LU0055631609",
      "assetName": "BlackRock Global Funds - World Gold Fund A2",
      "assetShortName": "GOLD",
      "assetCategory": "Stock",
      "assetSubCategory": "",
      "marketID": "CCLX",
      "sector": "Sector Equity Precious Metals",
      "industry": "",
      "timestamp": "2018-01-02"
    },
    {
      "ISIN": "LU0055631609",
      "assetName": "BlackRock Global Funds - World Gold Fund A2",
      "assetShortName": "GOLD",
      "assetCategory": "MTF",
      "assetSubCategory": "Equity",
      "marketID": "CCLX",
      "sector": "",
      "industry": "",
      "timestamp": "2018-01-02"
    },
    {
      "ISIN": "IE00B66F4759",
      "assetName": "iShares € High Yield Corp Bond UCITS ETF EUR (Dist) | IHYG",
      "assetShortName": "HY",
      "assetCategory": "Stock",
      "assetSubCategory": "",
      "marketID": "XLON",
      "sector": "EUR High Yield Bond",
      "industry": "",
      "timestamp": "2018-01-02"
    },
    {
      "ISIN": "IE00B66F4759",
      "assetName": "iShares € High Yield Corp Bond UCITS ETF EUR (Dist) | IHYG",
      "assetShortName": "HY",
      "assetCategory": "MTF",
      "assetSubCategory": "Bond",
      "marketID": "XLON",
      "sector": "",
      "industry": "",
      "timestamp": "2018-01-02"
    },
    {
      "ISIN": "IE00BCRY6003",
      "assetName": "Ishares Usd Short Dur Hy Crp",
      "assetShortName": "SDHY",
      "assetCategory": "Stock",
      "assetSubCategory": "",
      "marketID": "XLON",
      "sector": "",
      "industry": "",
      "timestamp": "2018-04-27"
    },
    {
      "ISIN": "IE00BCRY6003",
      "assetName": "Ishares Usd Short Dur Hy Crp",
      "assetShortName": "SDHY",
      "assetCategory": "MTF",
      "assetSubCategory": "Other",
      "marketID": "XLON",
      "sector": "",
      "industry": "",
      "timestamp": "2018-04-27"
    }
  ],
  "questionnaire_sentinel_by_risk": {
    "Predicted_Conservative": 2842,
    "Predicted_Balanced": 1430,
    "Predicted_Income": 2704,
    "Predicted_Aggressive": 298,
    "Not_Available": 1
  },
  "limit_price_endpoint_or_roi_mismatches": [],
  "price_coverage_summary": {
    "assets_with_absent_weekdays_inside_span": 689,
    "absent_weekday_asset_date_pairs": 1697,
    "max_calendar_gap_days": 4,
    "first_date_range": [
      "2018-01-01",
      "2022-10-31"
    ],
    "last_date_range": [
      "2018-01-19",
      "2022-11-29"
    ]
  },
  "report_example": {
    "transaction": {
      "customerID": "00017496858921195E5A",
      "ISIN": "GRS434003000",
      "transactionID": "7590224",
      "transactionType": "Buy",
      "timestamp": "2020-03-27",
      "totalValue": "11000.0",
      "units": "5000.0",
      "channel": "Internet Banking",
      "marketID": "XATH"
    },
    "csv_record_line": 2,
    "all_rows_with_transaction_id": 1,
    "customer_history": [
      {
        "csv_record_line": 15853,
        "customerID": "00017496858921195E5A",
        "customerType": "Professional",
        "riskLevel": "Aggressive",
        "investmentCapacity": "CAP_GT300K",
        "lastQuestionnaireDate": "2020-03-13",
        "timestamp": "2021-02-01"
      },
      {
        "csv_record_line": 15854,
        "customerID": "00017496858921195E5A",
        "customerType": "Professional",
        "riskLevel": "Aggressive",
        "investmentCapacity": "CAP_GT300K",
        "lastQuestionnaireDate": "2020-03-13",
        "timestamp": "2021-01-05"
      },
      {
        "csv_record_line": 15855,
        "customerID": "00017496858921195E5A",
        "customerType": "Professional",
        "riskLevel": "Aggressive",
        "investmentCapacity": "CAP_GT300K",
        "lastQuestionnaireDate": "2020-03-13",
        "timestamp": "2020-03-27"
      },
      {
        "csv_record_line": 15856,
        "customerID": "00017496858921195E5A",
        "customerType": "Professional",
        "riskLevel": "Aggressive",
        "investmentCapacity": "CAP_GT300K",
        "lastQuestionnaireDate": "2020-03-13",
        "timestamp": "2021-03-19"
      }
    ],
    "asset_history": [
      {
        "csv_record_line": 338,
        "ISIN": "GRS434003000",
        "assetName": "PPC SA",
        "assetShortName": "ΔΕΗ",
        "assetCategory": "Stock",
        "assetSubCategory": "Large Cap",
        "marketID": "XATH",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "timestamp": "2018-01-02"
      }
    ],
    "same_day_price": [
      {
        "csv_record_line": 279095,
        "ISIN": "GRS434003000",
        "timestamp": "2020-03-27",
        "closePrice": "2.2"
      }
    ]
  }
}
```

Полное покрытие по каждому активу: `data/processed/far_trans_audit.json` → `checks.price_coverage_per_asset`.
