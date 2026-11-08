"""Markdown reports for the creator-first Fewgood replay (no API calls)."""
import argparse, json, statistics
from collections import Counter
from pathlib import Path
from .fewgood_report import table, cell, date_only, duration, views, link_title, reasons, judgment, usage_rows, days_old
from .fewgood_creators import ROOT, clickbait_signals, evidence_label

def load(path, default={}):
    path=Path(path); return json.loads(path.read_text()) if path.exists() else default
def pool_report(result):
    out=['# Fewgood 第 2 轮博主池','','数据来自 YouTube Data API；X 仅为公开线索。','']
    creators=result.get('creators',[])
    for topic in result.get('topics',[]):
      rows=[c for c in creators if c.get('status')=='included' and topic['id'] in c.get('subtopics',[])]
      out += ['## '+topic['name_zh'],'',table(['名称','语言','X','YouTube','订阅数','最近上传','入池依据'],[[c.get('name'),c.get('lang'),('@'+c['x']) if c.get('x') else '',f"https://www.youtube.com/channel/{c.get('channel_id')}" if c.get('channel_id') else '',c.get('subscriber_count','未知'),date_only(c.get('last_upload_at')), evidence_label(c.get('evidence',[]))] for c in rows]),'']
    excluded=[c for c in creators if c.get('status')!='included']
    out += ['## 未入池','',table(['名称','频道 ID','状态','原因'],[[c.get('name'),c.get('channel_id'),c.get('status'),c.get('reason')] for c in excluded]),'','## 统计','',table(['指标','值'],[[k,v] for k,v in result.get('creator_pool',{}).items()]),'']
    return '\n'.join(out)
def quality(result, usage, judgments):
    out=['# Fewgood 第 2 轮质量报告','','## usage','',table(['项目','值'],usage_rows(result,usage)),'']
    for t in result.get('topics',[]):
      out += ['## '+t['name_zh'],'', '### stats','',table(['指标','值'],[[k,v] for k,v in t.get('stats',{}).items()]),'', '### Top 6','',table(['#','标题','频道','发布日期','时长','播放量','推荐依据','初步相关性'],[[i,link_title(v),v.get('channel_title'),date_only(v.get('published_at')),duration(v.get('duration_seconds')),views(v.get('view_count')),'<br>'.join(v.get('reasons',[])),judgment(judgments,v.get('video_id'))] for i,v in enumerate(t.get('videos',[])[:6],1)]),'']
    return '\n'.join(out)
def metrics(rows, judgments, refreshed):
    verdict=[judgments.get(x.get('video_id'),{}).get('verdict','待评') for x in rows]
    days=[days_old(x.get('published_at'),refreshed) for x in rows]; days=[x for x in days if x is not None]
    return [sum(x=='相关' for x in verdict),sum(x=='部分相关' for x in verdict),sum(x=='不相关' for x in verdict),len({x.get('channel_id') or x.get('channel_title') for x in rows}),statistics.median(days) if days else '未知',sum(len(clickbait_signals(x.get('title',''))) for x in rows)]
def compare(r1,r2a,r2b,j1,j2a,j2b):
    out=['# Fewgood 轮次对比','','R1 = 第 1 轮 B；R2 = 第 2 轮 B（初版）；R2b = 第 2 轮修订（个人博主 ≥1000 订阅 + 同一事件只取 1 条，零 API 重放）；A = 第 1 轮普通搜索 baseline。均为 Top6。','','相关性均为 Grok Bot 根据标题和频道做的**初判**，未观看视频，待 Jason 复核。','']
    rows=[]; changes=[]; refresh=r2b.get('data_refreshed_at')
    o1={x['id']:x for x in r1.get('topics',[])}; o2={x['id']:x for x in r2a.get('topics',[])}
    aj=dict(j1); aj.update(j2a); aj.update(j2b)
    for t in r2b.get('topics',[]):
      tid=t['id']; b1=o1.get(tid,{}).get('videos',[])[:6]; b2=o2.get(tid,{}).get('videos',[])[:6]; b3=t.get('videos',[])[:6]; a=r2b.get('baseline',{}).get(tid,[])[:6]
      m1,m2,m3,ma=metrics(b1,j1,r1.get('data_refreshed_at')),metrics(b2,j2a,r2a.get('data_refreshed_at')),metrics(b3,j2b,refresh),metrics(a,aj,refresh)
      rows.append([t['name_zh'],f'{m1[0]}/{m1[1]}/{m1[2]}',f'{m2[0]}/{m2[1]}/{m2[2]}',f'{m3[0]}/{m3[1]}/{m3[2]}',f'{ma[0]}/{ma[1]}/{ma[2]}',m3[3],m3[4],m3[5],len({x.get('video_id') for x in b2}&{x.get('video_id') for x in b3})])
      i2={x.get('video_id') for x in b2}; i3={x.get('video_id') for x in b3}
      for v in b2:
        if v.get('video_id') not in i3: changes.append([t['name_zh'],'移出',v.get('channel_title',''),link_title(v)])
      for v in b3:
        if v.get('video_id') not in i2: changes.append([t['name_zh'],'补入',v.get('channel_title',''),link_title(v)])
      out += ['## '+t['name_zh'],'',table(['#','R2b Top6 标题','频道'],[[i,link_title(v),v.get('channel_title','')] for i,v in enumerate(b3,1)]),'']
    out += ['## 汇总（相关/部分相关/不相关，初判）','',table(['主题','R1','R2','R2b','A','R2b频道数','R2b中位天数','R2b营销信号','R2∩R2b'],rows),'']
    out += ['## R2 → R2b 变动','',table(['主题','变动','频道','视频'],changes) if changes else '无变动。','']
    return '\n'.join(out)
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--out-dir',type=Path,default=ROOT/'docs/mvp');p.add_argument('--result',type=Path,default=ROOT/'data/experiments/fewgood-r2-result.json');a=p.parse_args(argv)
 result=load(a.result); usage=load(ROOT/'data/experiments/fewgood-r2-usage.json'); j2=load(ROOT/'docs/mvp/preliminary-judgments-r2b.json')
 if not j2: j2=load(ROOT/'docs/mvp/preliminary-judgments-r2.json')
 r2a=load(ROOT/'data/experiments/fewgood-r2a-result.json'); j2a=load(ROOT/'docs/mvp/preliminary-judgments-r2.json');a.out_dir.mkdir(parents=True,exist_ok=True)
 (a.out_dir/'creator-pool-table.md').write_text(pool_report(result));(a.out_dir/'round2-quality.md').write_text(quality(result,usage,j2));r1=load(ROOT/'data/experiments/fewgood-mvp-result.json');j1=load(ROOT/'docs/mvp/preliminary-judgments.json');(a.out_dir/'round-compare.md').write_text(compare(r1,r2a,result,j1,j2a,j2))
if __name__=='__main__':main()
