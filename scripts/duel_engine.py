"""
duel_engine.py
Standalone version of the DUEL relative-scoring algorithm and SEC EDGAR fetcher.

This is a stripped-down extract of the core logic used on https://duelstocks.com
It intentionally does NOT include:
  - the Flask web app / database caching
  - payment processing
  - PDF report generation
  - DCF valuation and Resilience (STR) report — those remain PRO features
    available only on the main site.

Only the base 8-factor relative comparison is reproduced here.
"""

import asyncio
import json
from datetime import datetime, timedelta

import aiohttp

# ════════════════════════════════════════════════════════════
# 8-FACTOR ALGORITHM
# ════════════════════════════════════════════════════════════

DEFAULT_WEIGHTS = {
    'revenue_growth':   0.16,
    'op_cash_margin':   0.15,
    'roic':             0.15,
    'sloan_ratio':      0.12,
    'asset_turnover':   0.10,
    'recv_turnover':    0.08,
    'operating_margin': 0.12,
    'fcf_margin':       0.12,
}

INVERTED = {'sloan_ratio'}

FACTOR_LABELS = {
    'revenue_growth':   'Revenue Growth (3Y CAGR)',
    'op_cash_margin':   'Operating Cash Flow Margin',
    'roic':             'Return on Invested Capital',
    'sloan_ratio':      'Sloan Ratio (lower is better)',
    'asset_turnover':   'Asset Turnover',
    'recv_turnover':    'Receivables Turnover',
    'operating_margin': 'Operating Margin',
    'fcf_margin':       'Free Cash Flow Margin',
}


def normalize_pair(a_val, b_val, inverted=False):
    if a_val is None and b_val is None:
        return 0.5, 0.5
    if a_val is None:
        return 0.35, 0.65
    if b_val is None:
        return 0.65, 0.35
    if a_val == b_val:
        return 0.5, 0.5

    lo, hi = min(a_val, b_val), max(a_val, b_val)
    spread = hi - lo
    if spread == 0:
        return 0.5, 0.5

    an = (a_val - lo) / spread
    bn = (b_val - lo) / spread

    if inverted:
        return 1 - an, 1 - bn
    return an, bn


def compute_duel(data_a, data_b, weights=None):
    weights = weights or DEFAULT_WEIGHTS
    factors = []
    total_a = 0.0
    total_b = 0.0

    for key, weight in weights.items():
        inv = key in INVERTED
        sa, sb = normalize_pair(data_a.get(key), data_b.get(key), inverted=inv)

        factors.append({
            'key': key,
            'label': FACTOR_LABELS.get(key, key),
            'weight': weight,
            'a_raw': data_a.get(key),
            'b_raw': data_b.get(key),
            'a_score': round(sa, 4),
            'b_score': round(sb, 4),
        })
        total_a += sa * weight
        total_b += sb * weight

    score_a = round(total_a * 100)
    score_b = round(total_b * 100)

    if score_a + score_b != 100:
        diff = 100 - (score_a + score_b)
        if score_a >= score_b:
            score_a += diff
        else:
            score_b += diff

    winner = data_a['ticker'] if score_a >= score_b else data_b['ticker']
    gap = abs(score_a - score_b)

    if gap >= 20:
        strength = 'dominant'
    elif gap >= 12:
        strength = 'clear'
    elif gap >= 5:
        strength = 'moderate'
    else:
        strength = 'slight'

    return {
        'score_a': score_a,
        'score_b': score_b,
        'winner': winner,
        'strength': strength,
        'gap': gap,
        'factors': factors,
    }


# ════════════════════════════════════════════════════════════
# PERIOD HELPERS
# ════════════════════════════════════════════════════════════

def get_period_type(entry):
    try:
        if not entry.get('end'):
            return "unknown"
        end = datetime.strptime(entry.get('end'), '%Y-%m-%d')
        start_str = entry.get('start')
        if start_str:
            start = datetime.strptime(start_str, '%Y-%m-%d')
            days = (end - start).days
            if 80 <= days <= 105:
                return "Q"
            elif 350 <= days <= 385:
                return "Y"
            else:
                return f"{days}d"
    except Exception:
        pass
    return "unknown"


def get_period_type_from_date(date_str):
    if not date_str:
        return "unknown"
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        if dt.month == 12 and dt.day == 31:
            return "Y"
        if dt.month in (3, 6, 9):
            return "Q"
        return "unknown"
    except Exception:
        return "unknown"


def safe_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return round(f, 4) if f == f and abs(f) != float('inf') else None
    except (TypeError, ValueError):
        return None


# ════════════════════════════════════════════════════════════
# SEC EDGAR FETCHING
# ════════════════════════════════════════════════════════════

SEC_HEADERS = {'User-Agent': 'DuelStocksGitHubDemo/1.0 contact@duelstocks.com'}


async def async_http_get(session, url, timeout=30):
    try:
        async with session.get(url, headers=SEC_HEADERS, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
            if response.status != 200:
                print(f"  HTTP {response.status} for {url}")
                return None
            return await response.text()
    except Exception as e:
        print(f"  ERROR fetching {url}: {type(e).__name__}: {e}")
        return None


async def get_ciks_for_ticker_async(session, ticker):
    ticker = ticker.upper().strip()
    url = 'https://www.sec.gov/files/company_tickers.json'
    raw_data = await async_http_get(session, url, timeout=20)
    ciks = []
    if raw_data:
        try:
            data = json.loads(raw_data)
            for item in data.values():
                if item.get('ticker', '').upper() == ticker:
                    cik = str(item['cik_str']).zfill(10)
                    if cik not in ciks:
                        ciks.append(cik)
        except Exception:
            pass
    return ciks or None


async def async_sec_get_fact(session, gaap, concepts, max_age_months=6, prefer_annual=False):
    now = datetime.now()
    cutoff_date = now - timedelta(days=max_age_months * 30)
    allowed_forms = {'10-K', '10-Q', '10-K/A', '10-Q/A'}
    all_entries = []
    for concept in concepts:
        units = gaap.get(concept, {}).get('units', {})
        for unit_type, entries in units.items():
            if unit_type not in ('USD', 'shares'):
                continue
            for e in entries:
                form = e.get('form')
                end_str = e.get('end')
                val = e.get('val')
                if val is None or not end_str:
                    continue
                if form and form not in allowed_forms:
                    continue
                try:
                    dt = datetime.strptime(end_str, '%Y-%m-%d')
                    if dt <= now:
                        period_type = get_period_type(e)
                        all_entries.append((dt, end_str, float(val), concept, period_type))
                except ValueError:
                    continue

    if not all_entries:
        return None, None, False, None

    if prefer_annual:
        annual_entries = [e for e in all_entries if e[4] == 'Y']
        if annual_entries:
            all_entries = annual_entries

    all_entries.sort(key=lambda x: x[0], reverse=True)
    best_dt, best_date, best_val, best_concept, best_period = all_entries[0]
    is_stale = best_dt < cutoff_date
    return best_val, best_date, is_stale, best_period


async def async_sec_get_fact_n_years_ago(session, gaap, concepts, n=3, prefer_annual=False):
    all_10k = []
    for concept in concepts:
        units = gaap.get(concept, {}).get('units', {})
        for unit_type, entries in units.items():
            if unit_type not in ('USD', 'shares'):
                continue
            for e in entries:
                form = e.get('form')
                if form in ('10-K', '10-K/A') and e.get('end') and e.get('val') is not None:
                    if prefer_annual and get_period_type(e) != 'Y':
                        continue
                    all_10k.append((e['end'], float(e['val'])))
    if not all_10k:
        return None, None
    unique = {}
    for date_str, val in all_10k:
        unique[date_str] = max(unique.get(date_str, val), val)
    sorted_10k = sorted(unique.items(), key=lambda x: x[0], reverse=True)
    if len(sorted_10k) > n:
        return sorted_10k[n]
    return sorted_10k[-1]


async def async_build_company_data(session, ticker):
    """Fetch + derive the 8 base factors for one ticker from SEC EDGAR XBRL data."""
    ticker = ticker.upper().strip()

    ciks = await get_ciks_for_ticker_async(session, ticker)
    if not ciks:
        return None
    ciks.sort(key=lambda x: int(x) if x.isdigit() else 0, reverse=True)

    used_cik, facts, gaap, best_date = None, None, None, None
    for cik in ciks:
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        raw_facts = await async_http_get(session, facts_url, timeout=40)
        if not raw_facts:
            continue
        try:
            current_facts = json.loads(raw_facts)
            current_gaap = current_facts.get('facts', {}).get('us-gaap', {})
            if not current_gaap:
                continue
            check_tags = ['Assets', 'Revenues', 'NetIncomeLoss', 'OperatingIncomeLoss']
            dates = []
            for tag in check_tags:
                entries = current_gaap.get(tag, {}).get('units', {}).get('USD', [])
                if entries:
                    latest_e = max(entries, key=lambda x: x.get('end', ''))
                    if latest_e.get('end'):
                        dates.append(latest_e.get('end'))
            if dates:
                latest_date_str = max(dates)
                if best_date is None or latest_date_str > best_date:
                    best_date, facts, gaap, used_cik = latest_date_str, current_facts, current_gaap, cik
        except Exception:
            continue

    if not facts or not gaap:
        return None

    revenue_tags = [
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomer", "SalesRevenueNet",
        "SalesRevenueGoodsNet", "NetSales", "SalesRevenue"
    ]
    revenue, rev_date, rev_stale, rev_period = await async_sec_get_fact(session, gaap, revenue_tags, prefer_annual=True)
    rev_3y, rev_3y_date = await async_sec_get_fact_n_years_ago(session, gaap, revenue_tags, n=3, prefer_annual=True)

    revenue_growth = None
    if revenue and rev_3y and rev_3y > 0:
        rev_3y_period = get_period_type_from_date(rev_3y_date) if rev_3y_date else "unknown"
        if rev_period == 'Q' and (rev_3y_period == 'Y' or rev_3y / revenue > 3.5):
            rev_3y_adj = rev_3y / 4.0
            revenue_growth = (pow(revenue / rev_3y_adj, 1 / 3) - 1) * 100
        else:
            revenue_growth = (pow(revenue / rev_3y, 1 / 3) - 1) * 100

    cfo, *_ = await async_sec_get_fact(session, gaap, ['NetCashProvidedByUsedInOperatingActivities'], prefer_annual=True)
    cfi, *_ = await async_sec_get_fact(session, gaap, ['NetCashProvidedByUsedInInvestingActivities'])
    net_income, *_ = await async_sec_get_fact(session, gaap, ['NetIncomeLoss', 'NetIncome'])
    total_assets, *_ = await async_sec_get_fact(session, gaap, ['Assets'], prefer_annual=True)
    equity, *_ = await async_sec_get_fact(session, gaap, [
        'StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'
    ])
    lt_debt, *_ = await async_sec_get_fact(session, gaap, ['LongTermDebt', 'LongTermDebtNoncurrent', 'LongTermDebtAndCapitalLeaseObligations'])
    st_debt, *_ = await async_sec_get_fact(session, gaap, ['ShortTermBorrowings', 'DebtCurrent', 'ShortTermDebt'])
    cash, *_ = await async_sec_get_fact(session, gaap, ['CashAndCashEquivalentsAtCarryingValue', 'Cash', 'CashAndCashEquivalents'])
    op_income, *_ = await async_sec_get_fact(session, gaap, ['OperatingIncomeLoss', 'IncomeFromOperations'], prefer_annual=True)
    receivables, *_ = await async_sec_get_fact(session, gaap, [
        'AccountsReceivableNetCurrent', 'AccountsReceivableNet', 'AccountsReceivable',
        'ReceivablesNetCurrent', 'TradeAndOtherReceivablesCurrent', 'AccountsReceivableGross'
    ], prefer_annual=True)
    capex_direct, *_ = await async_sec_get_fact(session, gaap, [
        'CapitalExpenditures', 'PaymentsForCapitalExpenditures',
        'PurchaseOfPropertyPlantAndEquipment', 'PaymentsToAcquirePropertyPlantAndEquipment'
    ], prefer_annual=True)
    capex = capex_direct if capex_direct is not None else (-cfi if cfi is not None and cfi < 0 else 0)

    op_cash_margin = (cfo / revenue) * 100 if cfo and revenue and revenue > 0 else None

    roic = None
    if op_income and equity and cash is not None:
        total_debt = (lt_debt or 0) + (st_debt or 0)
        invested_capital = equity + total_debt - cash
        if invested_capital > 0:
            roic = ((op_income * 0.75) / invested_capital) * 100

    sloan_ratio = None
    if net_income is not None and cfo is not None and total_assets and total_assets > 0:
        sloan_ratio = ((net_income - cfo - (cfi or 0)) / total_assets) * 100

    asset_turnover = revenue / total_assets if revenue and total_assets and total_assets > 0 else None
    recv_turnover = revenue / receivables if revenue and receivables and receivables > 0 else None
    operating_margin = (op_income / revenue) * 100 if op_income and revenue and revenue > 0 else None
    fcf_margin = ((cfo - capex) / revenue) * 100 if cfo is not None and capex is not None and revenue and revenue > 0 else None

    report_date = rev_date or "unknown"

    return {
        'ticker': ticker,
        'revenue_growth': safe_float(revenue_growth),
        'op_cash_margin': safe_float(op_cash_margin),
        'roic': safe_float(roic),
        'sloan_ratio': safe_float(sloan_ratio),
        'asset_turnover': safe_float(asset_turnover),
        'recv_turnover': safe_float(recv_turnover),
        'operating_margin': safe_float(operating_margin),
        'fcf_margin': safe_float(fcf_margin),
        'report_date': report_date,
        'used_cik': used_cik,
    }


async def fetch_pair(ticker_a, ticker_b):
    async with aiohttp.ClientSession() as session:
        data_a = await async_build_company_data(session, ticker_a)
        data_b = await async_build_company_data(session, ticker_b)
    if not data_a or not data_b:
        return None
    result = compute_duel(data_a, data_b)
    return {'a': data_a, 'b': data_b, 'result': result}
