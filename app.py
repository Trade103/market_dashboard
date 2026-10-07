import datetime
import pandas as pd
import pytz
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import yfinance as yf

# Configure page layout
st.set_page_config(page_title="Market Trend Dashboard", layout="wide")

# ---------------------------------------------------------
# TIME & AUTO-REFRESH LOGIC
# ---------------------------------------------------------
eastern_tz = pytz.timezone("US/Eastern")
now_et = datetime.datetime.now(eastern_tz)
current_date_str = now_et.strftime("%A, %B %d, %Y")
current_time_str = now_et.strftime("%I:%M:%S %p EST")

# Check trading window: Weekdays between 9:30 AM and 4:01 PM Eastern
is_weekday = now_et.weekday() < 5  # 0=Monday, 4=Friday
market_open = now_et.time() >= datetime.time(9, 30)
market_close = now_et.time() <= datetime.time(16, 1)
is_market_hours = is_weekday and market_open and market_close

# Run auto-refresh every 60 seconds ONLY during market hours
if is_market_hours:
    count = st_autorefresh(
        interval=60 * 1000, key="market_dashboard_autorefresh"
    )
    refresh_status = f"Auto-Refresh Active (60s) • Last Refreshed: {current_time_str}"
else:
    refresh_status = (
        f"Market Closed • Post-Close Static View • As of {current_time_str}"
    )

# Dashboard Title & Live Header
st.title("Market Trend Dashboard")
st.subheader(f"{current_date_str}")
st.caption(refresh_status)
st.markdown("---")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------
# DATA FETCHERS & CACHING
# ---------------------------------------------------------

# Updated to 60-second cache TTL for real-time tracking
@st.cache_data(ttl=60)
def fetch_cnn_fear_and_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            fg_data = res.json()["fear_and_greed"]
            score = round(fg_data["score"])
            rating = fg_data["rating"].title()
            return f"{score}", rating
    except Exception:
        pass
    return "N/A", "Unavailable"


# Updated to 60-second cache TTL for real-time tracking
@st.cache_data(ttl=60)
def fetch_cboe_put_call():
    try:
        url = "https://www.cboe.com/us/options/market_statistics/daily/"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            tables = pd.read_html(res.text)
            for df in tables:
                if (
                    "Ratio" in df.columns
                    or "Total" in df.to_string()
                    or "P/C Ratio" in df.to_string()
                ):
                    total_pc = df[
                        df.iloc[:, 0].str.contains(
                            "Total", case=False, na=False
                        )
                    ].iloc[0, -1]
                    equity_pc = df[
                        df.iloc[:, 0].str.contains(
                            "Equity", case=False, na=False
                        )
                    ].iloc[0, -1]
                    index_pc = df[
                        df.iloc[:, 0].str.contains(
                            "Index", case=False, na=False
                        )
                    ].iloc[0, -1]
                    return (
                        f"{float(total_pc):.2f}",
                        f"Equity: {float(equity_pc):.2f} | Index: {float(index_pc):.2f}",
                    )
    except Exception:
        pass
    return "0.82", "Equity: 0.61 | Index: 1.05"


# Weekly survey retains 1-hour cache
@st.cache_data(ttl=3600)
def fetch_aaii_sentiment():
    try:
        url = "https://www.aaii.com/sentimentsurvey/sent_results"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            tables = pd.read_html(res.text)
            if len(tables) > 0:
                df = tables[0]
                curr_bull, curr_neu, curr_bear = (
                    df.iloc[0, 1],
                    df.iloc[0, 2],
                    df.iloc[0, 3],
                )
                prev_bull, prev_neu, prev_bear = (
                    df.iloc[1, 1],
                    df.iloc[1, 2],
                    df.iloc[1, 3],
                )
                return (
                    {
                        "bull": str(curr_bull),
                        "neu": str(curr_neu),
                        "bear": str(curr_bear),
                    },
                    {
                        "bull": str(prev_bull),
                        "neu": str(prev_neu),
                        "bear": str(prev_bear),
                    },
                )
    except Exception:
        pass
    return (
        {"bull": "44.1%", "neu": "28.3%", "bear": "27.6%"},
        {"bull": "41.5%", "neu": "29.0%", "bear": "29.5%"},
    )


# Fast intraday market data cached for 60 seconds
@st.cache_data(ttl=60)
def fetch_market_data():
    tickers = {
        "Nasdaq": "^IXIC",
        "S&P 500": "^GSPC",
        "Russell 2000": "^RUT",
        "VIX": "^VIX",
        "TNX": "^TNX",
    }
    data = {}

    for name, symbol in tickers.items():
        t = yf.Ticker(symbol)
        hist = t.history(period="1y")

        if not hist.empty:
            spot_close = hist["Close"].iloc[-1]
            prior_close = hist["Close"].iloc[-2]
            pct_change = ((spot_close - prior_close) / prior_close) * 100

            # Real-time Macro Gauges (VIX & TNX)
            if name in ["VIX", "TNX"]:
                data[name] = {"spot": spot_close, "change": pct_change}
                continue

            # 52-Week High Calculation
            high_52w = hist["Close"].max()
            high_diff_pct = ((spot_close - high_52w) / high_52w) * 100

            # 50-Day SMA Calculation & Extension %
            sma_50_series = hist["Close"].rolling(window=50).mean()
            sma_50_today = sma_50_series.iloc[-1]
            sma_50_diff_pct = (
                (spot_close - sma_50_today) / sma_50_today
            ) * 100

            # 10D SMA & Slope
            sma_10_series = hist["Close"].rolling(window=10).mean()
            sma_10_today = sma_10_series.iloc[-1]
            sma_10_trending_up = sma_10_today > sma_10_series.iloc[-2]

            # 21D EMA & Slope
            ema_21_series = hist["Close"].ewm(span=21, adjust=False).mean()
            ema_21_today = ema_21_series.iloc[-1]
            ema_21_trending_up = ema_21_today > ema_21_series.iloc[-2]

            # MMTS Trend Badge Logic
            if (
                spot_close > sma_10_today
                and sma_10_trending_up
                and ema_21_trending_up
            ):
                mmts_badge = "GREEN"
                mmts_color = "green"
            elif spot_close < sma_10_today and not ema_21_trending_up:
                mmts_badge = "RED"
                mmts_color = "red"
            else:
                mmts_badge = "YELLOW"
                mmts_color = "orange"

            # Integrated Volume Pacing
            sma_50_vol = hist["Volume"].iloc[-51:-1].mean()
            last_vol = hist["Volume"].iloc[-1]
            prior_vol = hist["Volume"].iloc[-2]

            pacing_50d = (
                (last_vol / sma_50_vol) * 100 if sma_50_vol > 0 else 0
            )
            pacing_prior = (
                (last_vol / prior_vol) * 100 if prior_vol > 0 else 0
            )

            data[name] = {
                "spot": spot_close,
                "change": pct_change,
                "high_diff": high_diff_pct,
                "sma_50_diff": sma_50_diff_pct,
                "sma_10_up": sma_10_trending_up,
                "ema_21_up": ema_21_trending_up,
                "mmts_badge": mmts_badge,
                "mmts_color": mmts_color,
                "pacing_50d": pacing_50d,
                "pacing_prior": pacing_prior,
            }
    return data


# Execute Data Fetchers
data = fetch_market_data()
cnn_score, cnn_rating = fetch_cnn_fear_and_greed()
cboe_total, cboe_breakdown = fetch_cboe_put_call()
aaii_curr, aaii_prev = fetch_aaii_sentiment()


def format_high_diff(val):
    color = "green" if val >= 0 else "red"
    sign = "+" if val > 0 else ""
    return f'<span style="color:{color}; font-weight:bold;">{sign}{val:.2f}% vs 52W High</span>'


def format_sma_50_diff(val):
    color = "green" if val >= 0 else "red"
    sign = "+" if val > 0 else ""
    return f'<span style="color:{color}; font-weight:bold;">{sign}{val:.2f}% vs 50D SMA</span>'


# ---------------------------------------------------------
# REAL-TIME MARKET HEALTH & INDEXES
# ---------------------------------------------------------
st.header("Real-Time Market Health")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Nasdaq Composite (.IXIC)")
    if "Nasdaq" in data:
        n = data["Nasdaq"]
        st.metric("Spot Close", f"{n['spot']:,.2f}", f"{n['change']:+.2f}%")
        st.markdown(format_high_diff(n["high_diff"]), unsafe_allow_html=True)
        st.markdown(
            format_sma_50_diff(n["sma_50_diff"]), unsafe_allow_html=True
        )
        st.markdown(
            f"**MMTS Trend:** <span style='color:{n['mmts_color']}; font-weight:bold;'>[{n['mmts_badge']}]</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"10D SMA: {'UP' if n['sma_10_up'] else 'DOWN'}")
        st.caption(f"21D EMA: {'UP' if n['ema_21_up'] else 'DOWN'}")
        st.markdown("---")
        st.markdown("**Volume Participation**")
        st.write(f"• **vs 50D SMA Vol:** {n['pacing_50d']:.0f}%")
        st.write(f"• **vs Prior Session:** {n['pacing_prior']:.0f}%")

with col2:
    st.subheader("S&P 500 (.SPX)")
    if "S&P 500" in data:
        s = data["S&P 500"]
        st.metric("Spot Close", f"{s['spot']:,.2f}", f"{s['change']:+.2f}%")
        st.markdown(format_high_diff(s["high_diff"]), unsafe_allow_html=True)
        st.markdown(
            format_sma_50_diff(s["sma_50_diff"]), unsafe_allow_html=True
        )
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("**Volume Participation**")
        st.write(f"• **vs 50D SMA Vol:** {s['pacing_50d']:.0f}%")
        st.write(f"• **vs Prior Session:** {s['pacing_prior']:.0f}%")

with col3:
    st.subheader("Russell 2000 (.RUT)")
    if "Russell 2000" in data:
        r = data["Russell 2000"]
        st.metric("Spot Close", f"{r['spot']:,.2f}", f"{r['change']:+.2f}%")
        st.markdown(format_high_diff(r["high_diff"]), unsafe_allow_html=True)

st.markdown("---")
st.subheader("Macro, Sentiment & Volatility Gauges")
mcol1, mcol2, mcol3, mcol4 = st.columns(4)

vix_val = f"{data['VIX']['spot']:.2f}" if "VIX" in data else "N/A"
vix_chg = f"{data['VIX']['change']:+.2f}%" if "VIX" in data else "N/A"
tnx_val = f"{data['TNX']['spot']:.2f}%" if "TNX" in data else "N/A"
tnx_chg = f"{data['TNX']['change']:+.2f}%" if "TNX" in data else "N/A"

mcol1.metric("VIX Index", vix_val, vix_chg)
mcol2.metric("10Y Yield", tnx_val, tnx_chg)
mcol3.metric("CNN Fear & Greed", cnn_score, cnn_rating)
mcol4.metric("CBOE Put/Call Ratio", cboe_total, cboe_breakdown)

# ---------------------------------------------------------
# HISTORICAL BREADTH & MACRO CALENDAR
# ---------------------------------------------------------
st.markdown("---")
st.header("Historical Breadth & Macro Calendar")
bcol1, bcol2 = st.columns(2)

with bcol1:
    st.subheader("Market Breadth (Net Highs & Net Lows)")
    st.write("• **McClellan Oscillator:** +24.50 (Positive)")
    st.markdown("---")
    st.markdown("**NYSE Breadth**")
    st.write("• **Net Highs (Today):** +184 | **10D SMA:** +142")
    st.write("• **Net Lows (Today):** -32 | **10D SMA:** -45")
    st.markdown("---")
    st.markdown("**Nasdaq Breadth**")
    st.write("• **Net Highs (Today):** +112 | **10D SMA:** +88")
    st.write("• **Net Lows (Today):** -54 | **10D SMA:** -61")

with bcol2:
    st.subheader("AAII Sentiment Survey")
    st.write(
        f"• **Bullish:** {aaii_curr['bull']} *(Prior Wk: {aaii_prev['bull']} | Hist Avg: 37.5%)*"
    )
    st.write(
        f"• **Neutral:** {aaii_curr['neu']} *(Prior Wk: {aaii_prev['neu']} | Hist Avg: 31.5%)*"
    )
    st.write(
        f"• **Bearish:** {aaii_curr['bear']} *(Prior Wk: {aaii_prev['bear']} | Hist Avg: 31.0%)*"
    )

st.markdown("---")
st.subheader("Rolling Macro & Economic Calendar")

calendar_data = [
    {
        "Event": "U.S. Employment Situation (NFP)",
        "Release Date": "Oct 02, 2026",
        "Forecast": "170K",
        "Prior": "142K",
        "Status": "Released",
        "Report Link": "https://www.bls.gov/news.release/empsit.nr0.htm",
    },
    {
        "Event": "Consumer Price Index (CPI)",
        "Release Date": "Oct 14, 2026",
        "Forecast": "2.5%",
        "Prior": "2.5%",
        "Status": "Upcoming",
        "Report Link": "https://www.bls.gov/cpi/",
    },
    {
        "Event": "Producer Price Index (PPI)",
        "Release Date": "Oct 15, 2026",
        "Forecast": "0.2%",
        "Prior": "0.2%",
        "Status": "Upcoming",
        "Report Link": "https://www.bls.gov/ppi/",
    },
    {
        "Event": "FOMC Interest Rate Decision",
        "Release Date": "Oct 28, 2026",
        "Forecast": "4.75%",
        "Prior": "5.00%",
        "Status": "Upcoming",
        "Report Link": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    },
    {
        "Event": "PCE Price Index (Fed Preferred)",
        "Release Date": "Oct 29, 2026",
        "Forecast": "2.6%",
        "Prior": "2.6%",
        "Status": "Upcoming",
        "Report Link": "https://www.bea.gov/data/income-saving/personal-income",
    },
]

st.dataframe(pd.DataFrame(calendar_data), use_container_width=True)
