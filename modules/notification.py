import requests
from config import NTFY_TOPIC,NTFY_SERVER
def send_ntfy(title,message,url=None,priority="high"):
    if not NTFY_TOPIC: raise RuntimeError("Set NTFY_TOPIC in .env")
    headers={"Title":title,"Priority":priority}
    if url: headers["Click"]=url
    r=requests.post(f"{NTFY_SERVER}/{NTFY_TOPIC}",data=message.encode(),headers=headers,timeout=20)
    r.raise_for_status()
