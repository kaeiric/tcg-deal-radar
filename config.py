import os
from dotenv import load_dotenv
load_dotenv()
EBAY_CLIENT_ID=os.getenv("EBAY_CLIENT_ID","").strip()
EBAY_CLIENT_SECRET=os.getenv("EBAY_CLIENT_SECRET","").strip()
EBAY_MARKETPLACE_ID=os.getenv("EBAY_MARKETPLACE_ID","EBAY_US").strip()
NTFY_TOPIC=os.getenv("NTFY_TOPIC","").strip()
NTFY_SERVER=os.getenv("NTFY_SERVER","https://ntfy.sh").rstrip("/")
SCAN_INTERVAL_MINUTES=max(5,int(os.getenv("SCAN_INTERVAL_MINUTES","15")))
DEFAULT_TAX_RATE=float(os.getenv("DEFAULT_TAX_RATE","0.08875"))
MAX_RESULTS_PER_QUERY=min(200,max(10,int(os.getenv("MAX_RESULTS_PER_QUERY","50"))))
DB_PATH=os.path.join(os.path.dirname(__file__),"data","tcg_radar.db")
