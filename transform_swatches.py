#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transform_swatches.py v2.0 -- Production-Grade Bulk Swatch & Image Transformer CLI
====================================================================================
Reads a CSV/Excel file (or plain-text URL list) and:
  1. Downloads images concurrently with retries and connection pooling
  2. Generates swatches in multiple sizes / shapes using Pillow
  3. Smart naming: SKU column -> Name/Title column -> filename -> numeric fallback
  4. Writes outputs into a ZIP archive (flat / by-product / by-size layouts)
  5. Produces an Excel report of every processed image

Install:  pip install Pillow requests openpyxl tqdm

Examples:
  python transform_swatches.py --input catalog.xlsx --url-col "Image URL"
  python transform_swatches.py --input urls.txt --sizes 500,1000 --shape circle
  python transform_swatches.py --input images/ --sizes 300,600 --shape rounded
"""
import argparse, concurrent.futures, io, math, os, re, sys, time, zipfile
from pathlib import Path
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    sys.exit("pip install requests")
try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("pip install Pillow")
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill
except ImportError:
    sys.exit("pip install openpyxl")
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

VERSION = "2.0.0"
SHAPES = ["square","circle","rounded","pill","oval","diamond","hexagon"]
BG_PRESETS = {"white":(255,255,255,255),"black":(0,0,0,255),
              "transparent":(0,0,0,0),"gray":(128,128,128,255)}
SUPPORTED_EXTS = {".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}

def make_session(retries=3, timeout=30):
    s = requests.Session()
    from urllib3.util.retry import Retry
    retry = Retry(total=retries,backoff_factor=0.4,
                  status_forcelist=(429,500,502,503,504))
    from requests.adapters import HTTPAdapter
    a = HTTPAdapter(max_retries=retry,pool_connections=8,pool_maxsize=16)
    s.mount("http://",a); s.mount("https://",a)
    s.headers.update({"User-Agent":"SwatchCLI/"+VERSION,"Accept":"image/*,*/*"})
    return s

def smart_name(sku, row_name, fallback, idx):
    """SKU -> Name/Title -> filename -> 4-digit numeric"""
    raw = None
    if sku and str(sku).strip(): raw = str(sku).strip()
    elif row_name and str(row_name).strip(): raw = str(row_name).strip()
    elif fallback and str(fallback).strip(): raw = Path(fallback).stem.strip()
    if raw:
        safe = re.sub(r"[^\w\-_. ()]","_",raw).strip().replace(" ","_")
        if safe: return safe
    return f"swatch_{str(idx+1).zfill(4)}"

def download_image(url, session, timeout=30, cors_proxy=""):
    t = (cors_proxy+url) if cors_proxy else url
    r = session.get(t,timeout=timeout,stream=True); r.raise_for_status()
    import io
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    return img, url.split("/")[-1].split("?")[0] or "img.jpg"

def load_local(path):
    return Image.open(path).convert("RGBA"), Path(path).name

def detect_bbox(img, threshold=245):
    r,g,b,a = img.split(); w,h = img.size
    md=[255 if(av<128 or rv<threshold or gv<threshold or bv<threshold) else 0
        for rv,gv,bv,av in zip(r.getdata(),g.getdata(),b.getdata(),a.getdata())]
    m=Image.new("L",(w,h)); m.putdata(md)
    bb=m.getbbox(); return bb if bb else (0,0,w,h)

def smart_crop(img, size, engine="smart", thresh=245, pad=0.05):
    iw,ih = img.size
    if engine=="smart":
        x0,y0,x1,y1=detect_bbox(img,thresh)
        bw,bh=x1-x0,y1-y0; p=int(max(bw,bh)*pad)
        x0,y0=max(0,x0-p),max(0,y0-p); x1,y1=min(iw,x1+p),min(ih,y1+p)
        c=img.crop((x0,y0,x1,y1)); cw,ch=c.size; sq=max(cw,ch)
        canvas=Image.new("RGBA",(sq,sq),(0,0,0,0))
        canvas.paste(c,((sq-cw)//2,(sq-ch)//2),c)
        return canvas.resize((size,size),Image.LANCZOS)
    elif engine=="center":
        sq=min(iw,ih); l=(iw-sq)//2; t=(ih-sq)//2
        return img.crop((l,t,l+sq,t+sq)).resize((size,size),Image.LANCZOS)
    elif engine=="contain":
        rat=min(size/iw,size/ih); nw,nh=int(iw*rat),int(ih*rat)
        rs=img.resize((nw,nh),Image.LANCZOS)
        c=Image.new("RGBA",(size,size),(0,0,0,0))
        c.paste(rs,((size-nw)//2,(size-nh)//2),rs); return c
    elif engine=="cover":
        rat=max(size/iw,size/ih); nw,nh=int(iw*rat),int(ih*rat)
        rs=img.resize((nw,nh),Image.LANCZOS)
        return rs.crop(((nw-size)//2,(nh-size)//2,(nw+size)//2,(nh+size)//2))
    else:
        return img.resize((size,size),Image.LANCZOS)

def apply_shape(img, shape):
    w,h=img.size; mask=Image.new("L",(w,h),0); draw=ImageDraw.Draw(mask)
    if shape=="circle": draw.ellipse([0,0,w-1,h-1],fill=255)
    elif shape=="rounded":
        r=max(4,min(w,h)//8); draw.rounded_rectangle([0,0,w-1,h-1],radius=r,fill=255)
    elif shape=="pill":
        r=min(w,h)//2; draw.rounded_rectangle([0,0,w-1,h-1],radius=r,fill=255)
    elif shape=="oval": draw.ellipse([0,int(h*.1),w,int(h*.9)],fill=255)
    elif shape=="diamond": draw.polygon([(w//2,0),(w,h//2),(w//2,h),(0,h//2)],fill=255)
    elif shape=="hexagon":
        cx,cy=w//2,h//2; rv=min(cx,cy)
        pts=[(int(cx+rv*math.cos(math.radians(60*i-30))),
              int(cy+rv*math.sin(math.radians(60*i-30)))) for i in range(6)]
        draw.polygon(pts,fill=255)
    else: draw.rectangle([0,0,w,h],fill=255)
    res=Image.new("RGBA",(w,h),(0,0,0,0)); res.paste(img,mask=mask); return res

def gen_swatch(img,size,shape="square",engine="smart",bg=(255,255,255,255),
               thresh=245,pad=0.05,fmt="PNG"):
    import io
    c=smart_crop(img,size,engine=engine,thresh=thresh,pad=pad)
    m=apply_shape(c,shape)
    bg_img=Image.new("RGBA",(size,size),bg)
    bg_img.paste(m,mask=m.split()[3])
    buf=io.BytesIO()
    if fmt.upper() in ("JPEG","JPG"): bg_img.convert("RGB").save(buf,format="JPEG",quality=92,optimize=True)
    elif fmt.upper()=="WEBP": bg_img.save(buf,format="WEBP",quality=90)
    else: bg_img.save(buf,format="PNG",optimize=True)
    return buf.getvalue()

def read_input(path,sheet=None):
    ext=Path(path).suffix.lower()
    if ext in (".xlsx",".xls"):
        wb=openpyxl.load_workbook(path,read_only=True,data_only=True)
        ws=wb[sheet] if sheet else wb.active
        it=ws.iter_rows(values_only=True); hdrs=next(it)
        headers=[str(c).strip() if c is not None else f"col_{i}" for i,c in enumerate(hdrs)]
        return [dict(zip(headers,r)) for r in it]
    elif ext==".csv":
        import csv
        with open(path,newline="",encoding="utf-8-sig") as f: return list(csv.DictReader(f))
    elif ext in (".txt",""):
        with open(path,encoding="utf-8") as f:
            return [{"url":l.strip()} for l in f if l.strip().startswith("http")]
    raise ValueError(f"Unsupported: {ext}")

def auto_col(headers,pattern):
    for h in headers:
        if re.search(pattern,str(h),re.I): return h
    return None

def process_row(row,idx,session,args):
    res={"idx":idx,"sku":None,"row_name":None,"url":None,
         "swatches":{},"status":"ok","error":None,
         "output_names":{},"orig_filename":None,"ms":0}
    t0=time.time()
    try:
        uc=args.url_col or auto_col(list(row.keys()),r"(image|img|photo|url|src|thumb)")
        url=str(row.get(uc) or "").strip() if uc else ""
        res["url"]=url
        res["sku"]=str(row.get(args.sku_col) or "").strip() if args.sku_col else None
        res["row_name"]=str(row.get(args.name_col) or "").strip() if args.name_col else None
        if not re.match(r"^https?://",url,re.I): raise ValueError(f"No URL in row {idx+1}")
        img,fname=download_image(url,session,args.timeout,args.cors_proxy or "")
        res["orig_filename"]=fname
        base=smart_name(res["sku"],res["row_name"],fname,idx)
        ext_m={"PNG":"png","JPEG":"jpg","JPG":"jpg","WEBP":"webp"}
        ext=ext_m.get(args.output_format.upper(),"png")
        for sz in args.sizes:
            data=gen_swatch(img,sz,shape=args.shape,engine=args.crop_engine,
                            bg=BG_PRESETS.get(args.bg_color,(255,255,255,255)),
                            thresh=args.bg_threshold,pad=args.pad_pct/100,fmt=args.output_format)
            res["swatches"][sz]=data; res["output_names"][sz]=f"{base}_{sz}.{ext}"
    except Exception as e:
        res["status"]="error"; res["error"]=str(e)
    res["ms"]=int((time.time()-t0)*1000); return res

def process_folder(folder,args):
    results=[]
    for i,p in enumerate([p for p in Path(folder).rglob("*") if p.suffix.lower() in SUPPORTED_EXTS]):
        t0=time.time(); r={"idx":i,"sku":None,"row_name":None,"url":str(p),
           "swatches":{},"status":"ok","error":None,"output_names":{},"orig_filename":p.name,"ms":0}
        try:
            img,_=load_local(p); base=smart_name(None,None,p.stem,i)
            ext_m={"PNG":"png","JPEG":"jpg","WEBP":"webp"}; ext=ext_m.get(args.output_format.upper(),"png")
            for sz in args.sizes:
                data=gen_swatch(img,sz,shape=args.shape,engine=args.crop_engine,
                                bg=BG_PRESETS.get(args.bg_color,(255,255,255,255)),
                                thresh=args.bg_threshold,pad=args.pad_pct/100,fmt=args.output_format)
                r["swatches"][sz]=data; r["output_names"][sz]=f"{base}_{sz}.{ext}"
        except Exception as e: r["status"]="error"; r["error"]=str(e)
        r["ms"]=int((time.time()-t0)*1000); results.append(r)
    return results

def write_zip(results,out,layout="flat"):
    ok=[r for r in results if r["status"]=="ok"]
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as zf:
        for r in ok:
            base=(list(r["output_names"].values())[0].rsplit("_",1)[0]
                  if r["output_names"] else f"img_{r['idx']+1}")
            for sz,data in r["swatches"].items():
                fn=r["output_names"].get(sz,f"{base}_{sz}.png")
                arc=(fn if layout=="flat" else
                     (f"{sz}/{fn}" if layout=="by-size" else f"{base}/{fn}"))
                zf.writestr(arc,data)

def write_report(results,out):
    wb=openpyxl.Workbook(); ws=wb.active; ws.title="Report"
    ws.append(["#","Filename","SKU","Name","URL","Status","Error","Sizes","Output Names","ms"])
    for r in results:
        ws.append([r["idx"]+1,r.get("orig_filename",""),r.get("sku") or "",
                   r.get("row_name") or "",r.get("url") or "",r.get("status",""),
                   r.get("error") or "",
                   ", ".join(str(s) for s in r.get("swatches",{}).keys()),
                   ", ".join(r.get("output_names",{}).values()),r.get("ms",0)])
    for cell in ws[1]:
        cell.font=Font(bold=True,color="FFFFFF")
        cell.fill=PatternFill("solid",fgColor="2563EB")
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width=min(
            max(len(str(c.value or "")) for c in col)+2,50)
    wb.save(out)

def parse_args():
    p=argparse.ArgumentParser(description="Bulk Swatch Generator v"+VERSION,
                               formatter_class=argparse.RawDescriptionHelpFormatter,epilog=__doc__)
    p.add_argument("--input","-i",required=True,help="Excel/CSV/URL-list/folder")
    p.add_argument("--out","-o",default="swatches.zip"); p.add_argument("--report",default="swatch_report.xlsx")
    p.add_argument("--sizes","-s",default="300,600,1200"); p.add_argument("--shape",default="square",choices=SHAPES)
    p.add_argument("--crop-engine",default="smart",choices=["smart","center","contain","cover","stretch"])
    p.add_argument("--bg-color",default="white"); p.add_argument("--bg-threshold",default=245,type=int)
    p.add_argument("--pad-pct",default=5,type=float)
    p.add_argument("--format",default="PNG",choices=["PNG","JPEG","WEBP"],dest="output_format")
    p.add_argument("--concurrency","-c",default=8,type=int); p.add_argument("--retries",default=3,type=int)
    p.add_argument("--timeout",default=30,type=int); p.add_argument("--cors-proxy",default="")
    p.add_argument("--sheet",default=None); p.add_argument("--url-col",default=None,help="URL col (auto-detected)")
    p.add_argument("--sku-col",default=None,help="SKU col for smart naming")
    p.add_argument("--name-col",default=None,help="Name/Title col for smart naming")
    p.add_argument("--layout",default="flat",choices=["flat","by-product","by-size"])
    p.add_argument("--version","-v",action="store_true"); return p.parse_args()

def main():
    args=parse_args()
    if args.version: print(f"v{VERSION}"); return
    args.sizes=[int(s.strip()) for s in args.sizes.split(",") if s.strip().isdigit()]
    if not args.sizes: sys.exit("No valid sizes. Use --sizes 300,600,1200")
    print(f"\nBulk Swatch Generator v{VERSION}\nInput : {args.input}\nSizes : {args.sizes}\nShape : {args.shape}\n")
    if os.path.isdir(args.input):
        results=process_folder(args.input,args)
    else:
        rows=read_input(args.input,sheet=args.sheet)
        if not rows: sys.exit("No rows found.")
        hdrs=list(rows[0].keys())
        if not args.url_col:
            args.url_col=auto_col(hdrs,r"(image|img|photo|url|src|thumb)")
            if args.url_col: print(f"URL col   : {args.url_col!r}")
        if not args.sku_col:
            args.sku_col=auto_col(hdrs,r"^sku")
            if args.sku_col: print(f"SKU col   : {args.sku_col!r}")
        if not args.name_col:
            args.name_col=auto_col(hdrs,r"^(name|title|product)")
            if args.name_col: print(f"Name col  : {args.name_col!r}")
        print(f"Rows      : {len(rows)}\n")
        session=make_session(args.retries,args.timeout)
        results=[None]*len(rows)
        bar=tqdm(total=len(rows),desc="Processing",unit="img") if HAS_TQDM else None
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futs={pool.submit(process_row,rows[i],i,session,args):i for i in range(len(rows))}
            done=0
            for fut in concurrent.futures.as_completed(futs):
                i=futs[fut]
                try: results[i]=fut.result()
                except Exception as e:
                    results[i]={"idx":i,"status":"error","error":str(e),"swatches":{},
                                "output_names":{},"sku":None,"row_name":None,
                                "url":None,"orig_filename":None,"ms":0}
                done+=1
                if bar: bar.update(1)
                else: print(f"\r  {done}/{len(rows)}",end="",flush=True)
        if bar: bar.close()
        else: print()
    ok=sum(1 for r in results if r and r["status"]=="ok")
    err=len(results)-ok
    print(f"\nDone: {ok} OK, {err} errors")
    if ok>0: write_zip(results,args.out,args.layout); print(f"ZIP    : {args.out}")
    write_report(results,args.report); print(f"Report : {args.report}\n")
    if err>0: sys.exit(1)

if __name__=="__main__":
    main()
