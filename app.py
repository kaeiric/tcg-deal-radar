import pandas as pd
import streamlit as st
from modules.database import init_db,get_cards,add_card,save_price,get_listings,get_alert_count
from modules.scanner import run_scan
from config import DEFAULT_TAX_RATE,SCAN_INTERVAL_MINUTES

st.set_page_config(page_title="TCG Deal Radar",page_icon="🎴",layout="wide")
init_db()
st.title("TCG Deal Radar")
st.caption("Local eBay listing monitor · Pokémon TCG + One Piece TCG")

with st.sidebar:
    st.header("Scan settings")
    threshold=st.number_input("Minimum discount (%)",1.0,90.0,20.0,1.0)
    tax=st.number_input("Estimated sales tax (%)",0.0,20.0,DEFAULT_TAX_RATE*100,0.125)/100
    st.caption(f"Target scan interval: {SCAN_INTERVAL_MINUTES} minutes")
    if st.button("Run scan now",type="primary",use_container_width=True):
        with st.spinner("Querying eBay..."):
            result=run_scan(threshold,tax,True)
        st.session_state["scan_result"]=result
        st.success(f'{result["alerts_sent"]} alert(s) sent.')
    if "scan_result" in st.session_state: st.json(st.session_state["scan_result"])

cards=get_cards(); listings=get_listings()
a,b,c=st.columns(3)
a.metric("Watched variants",len(cards)); b.metric("Stored listings",len(listings)); c.metric("Alerts sent",get_alert_count())

t1,t2,t3,t4=st.tabs(["Dashboard","Watchlist","Import prices","Listings"])
with t1:
    st.subheader("Potential deals")
    deals=[x for x in listings if (x.get("discount_pct") or 0)>=threshold]
    if deals:
        df=pd.DataFrame(deals)
        st.dataframe(df[["game","card_name","language","title","landed_cost","discount_pct","item_url"]],use_container_width=True,hide_index=True,
                     column_config={"item_url":st.column_config.LinkColumn("eBay listing")})
    else: st.info("No saved listings currently meet the threshold.")
with t2:
    st.subheader("Add card variant")
    with st.form("card_form"):
        game=st.selectbox("Game",["Pokemon","One Piece"])
        name=st.text_input("Card name",placeholder="Lugia V")
        set_name=st.text_input("Set name",placeholder="Silver Tempest")
        number=st.text_input("Card number",placeholder="186/195")
        rarity=st.text_input("Rarity",placeholder="Alternate Art")
        language=st.selectbox("Language",["English","Japanese"])
        condition=st.selectbox("Target condition",["Near Mint","Lightly Played","Moderately Played"])
        if st.form_submit_button("Add to watchlist"):
            if not name.strip(): st.error("Card name is required.")
            else:
                add_card({"game":game,"card_name":name.strip(),"set_name":set_name.strip(),
                    "card_number":number.strip(),"rarity":rarity.strip(),"language":language,"condition_target":condition})
                st.success("Added or already exists."); st.rerun()
    if cards: st.dataframe(pd.DataFrame(cards),use_container_width=True,hide_index=True)
with t3:
    st.subheader("Import market-price references")
    st.write("Required CSV columns: game, card_name, language, market_price. Optional: set_name, card_number, condition, source.")
    sample=pd.DataFrame([{"game":"Pokemon","card_name":"Lugia V","set_name":"Silver Tempest","card_number":"186/195",
        "language":"English","market_price":165.0,"condition":"Near Mint","source":"TCGplayer manual reference"}])
    st.download_button("Download CSV template",sample.to_csv(index=False),"market_prices_template.csv","text/csv")
    up=st.file_uploader("Upload CSV",type=["csv"])
    if up is not None:
        df=pd.read_csv(up); st.dataframe(df,use_container_width=True)
        if st.button("Import CSV rows"):
            required={"game","card_name","language","market_price"}
            missing=required-set(df.columns)
            if missing: st.error("Missing columns: "+", ".join(sorted(missing)))
            else:
                for _,r in df.iterrows():
                    d={"game":str(r["game"]),"card_name":str(r["card_name"]),
                       "set_name":str(r.get("set_name","")) if pd.notna(r.get("set_name","")) else "",
                       "card_number":str(r.get("card_number","")) if pd.notna(r.get("card_number","")) else "",
                       "rarity":"","language":str(r["language"]),
                       "condition_target":str(r.get("condition","Near Mint"))}
                    add_card(d)
                all_cards=get_cards()
                for _,r in df.iterrows():
                    def val(k,default=""): return str(r.get(k,default)) if pd.notna(r.get(k,default)) else default
                    card=next((x for x in all_cards if x["game"].lower()==val("game").lower()
                        and x["card_name"].lower()==val("card_name").lower()
                        and (x["set_name"] or "").lower()==val("set_name").lower()
                        and (x["card_number"] or "").lower()==val("card_number").lower()
                        and x["language"].lower()==val("language").lower()),None)
                    if card: save_price(card["id"],float(r["market_price"]),val("source","CSV"),val("condition","Near Mint"))
                st.success(f"Imported {len(df)} row(s).")
with t4:
    st.subheader("Recent listings")
    if listings:
        df=pd.DataFrame(listings)
        st.dataframe(df,use_container_width=True,hide_index=True,
            column_config={"item_url":st.column_config.LinkColumn("eBay listing")})
    else: st.info("No listings yet. Add cards, import prices, configure API credentials, then scan.")
st.divider()
st.caption("MVP uses manually imported price references and heuristic matching. Verify card identity, language, condition, seller, shipping, and checkout total before purchase.")
