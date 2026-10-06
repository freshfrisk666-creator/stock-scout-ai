from __future__ import annotations
import json,math,sqlite3
from datetime import datetime,timezone
import pandas as pd
import yfinance as yf
DB_PATH="data/stock_scout.db";OUTPUT="dashboard/data.json"
def clean(v):
    if v is None:return None
    try:
        if pd.isna(v):return None
    except (TypeError,ValueError):pass
    if hasattr(v,"item"):
        try:v=v.item()
        except (AttributeError,ValueError):pass
    if isinstance(v,float) and not math.isfinite(v):return None
    return v
def signal(raw):
    if not raw:return {}
    try:d=json.loads(raw)
    except (TypeError,json.JSONDecodeError):return {}
    keys=["technical_score","trend","momentum","rsi","volume","breakout","risk_reward"]
    return {k:clean(d.get(k)) for k in keys if k in d}
def prices(tickers):
    if not tickers:return {}
    data=yf.download(tickers=tickers,period="1d",interval="5m",prepost=False,auto_adjust=False,group_by="ticker",progress=False,threads=False)
    if data is None or data.empty:return {}
    out={}
    for t in tickers:
        try:
            if isinstance(data.columns,pd.MultiIndex):
                if t in data.columns.get_level_values(0):f=data[t]
                elif t in data.columns.get_level_values(1):f=data.xs(t,axis=1,level=1)
                else:continue
            else:f=data
            c=f["Close"].dropna()
            if not c.empty:out[t]=float(c.iloc[-1])
        except Exception:pass
    return out
def main():
    with sqlite3.connect(DB_PATH) as c:
        p=pd.read_sql_query("SELECT * FROM positions WHERE portfolio_id='default'",c)
        st=pd.read_sql_query("SELECT cash FROM portfolio_state WHERE portfolio_id='default'",c)
    op=p[p.status=="OPEN"].copy();cl=p[p.status=="CLOSED"].copy();ts=op.ticker.astype(str).tolist() if not op.empty else [];px=prices(ts);opens=[]
    for _,x in op.iterrows():
        t=str(x.ticker);mark=px.get(t,float(x.entry_price));entry=float(x.entry_price);shares=int(x.shares);risk=entry-float(x.stop);pnl=(mark-entry)*shares;ret=(mark-entry)/entry if entry else None;r=(mark-entry)/risk if risk>0 else None;ed=pd.to_datetime(x.entry_date,utc=True,errors="coerce");days=None
        if pd.notna(ed):days=max(0,(pd.Timestamp.now(tz="UTC")-ed).total_seconds()/86400)
        opens.append({"id":int(x.id),"rank":int(x['rank']),"ticker":t,"entry_date":str(x.entry_date),"entry_price":entry,"mark_price":mark,"shares":shares,"notional":float(x.notional),"stop":float(x.stop),"target":float(x.target),"unrealized_pnl":pnl,"unrealized_return":ret,"current_r":r,"holding_days":days,"strategy_type":x.get("strategy_type") or "SWING","planned_horizon_sessions":int(x.get("planned_horizon_sessions") or 20),"signal":signal(x.get("signal_snapshot"))})
    closed=[]
    for _,x in cl.sort_values("exit_date",ascending=False).iterrows():
        e=float(x.entry_price);ex=clean(x.exit_price);rp=clean(x.realized_pnl);closed.append({"id":int(x.id),"ticker":str(x.ticker),"entry_date":str(x.entry_date),"entry_price":e,"exit_date":clean(x.exit_date),"exit_price":ex,"realized_pnl":rp,"realized_return":((float(ex)-e)/e if ex is not None and e else None),"close_reason":clean(x.close_reason)})
    cash=float(st.iloc[0].cash) if not st.empty else 0;mv=sum(x["mark_price"]*x["shares"] for x in opens);up=sum(x["unrealized_pnl"] for x in opens);rp=sum(x["realized_pnl"] or 0 for x in closed);eq=cash+mv
    data={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"cash":cash,"market_value":mv,"equity":eq,"unrealized_pnl":up,"realized_pnl":rp,"open_positions":len(op),"closed_positions":len(closed)},"open":opens,"closed":closed}
    with open(OUTPUT,"w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2,default=clean)
    print(f"Dashboard data written: {OUTPUT}; Open: {len(op)}; Closed: {len(closed)}; Equity: {eq:.2f}")
if __name__=="__main__":main()
