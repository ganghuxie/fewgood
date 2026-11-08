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
def compare(r1,r2,j1,j2):
    out=['# Fewgood 两轮对比','','第 1 轮 B 与第 2 轮 B 均为 Top6；A 为第 1 轮原始 baseline。','']
    rows=[]; refresh=r2.get('data_refreshed_at')
    old={x['id']:x for x in r1.get('topics',[])}
    for t in r2.get('topics',[]):
      tid=t['id']; b1=old.get(tid,{}).get('videos',[])[:6]; b2=t.get('videos',[])[:6]; a=r2.get('baseline',{}).get(tid,[])[:6]
      # Baseline/A entries may be reviewed in either round; round 2 wins on overlap.
      a_judgments=dict(j1); a_judgments.update(j2)
      rows.append([t['name_zh'],*metrics(b1,j1,r1.get('data_refreshed_at')), *metrics(b2,j2,refresh),*metrics(a,a_judgments,refresh),len({x.get('video_id') for x in b1}&{x.get('video_id') for x in b2})])
      out += ['## '+t['name_zh'],'',table(['#','第 2 轮 Top6 标题'],[[i,link_title(v)] for i,v in enumerate(b2,1)]),'']
    out += ['## 汇总','',table(['主题','R1相关','R1部分','R1不相关','R1频道','R1中位天数','R1营销信号','R2相关','R2部分','R2不相关','R2频道','R2中位天数','R2营销信号','A相关','A部分','A不相关','A频道','A中位天数','A营销信号','两轮重叠'],rows),'']
    return '\n'.join(out)
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--out-dir',type=Path,default=ROOT/'docs/mvp');p.add_argument('--result',type=Path,default=ROOT/'data/experiments/fewgood-r2-result.json');a=p.parse_args(argv)
 result=load(a.result); usage=load(ROOT/'data/experiments/fewgood-r2-usage.json'); j2=load(ROOT/'docs/mvp/preliminary-judgments-r2.json'); r1=load(ROOT/'data/experiments/fewgood-mvp-result.json');j1=load(ROOT/'docs/mvp/preliminary-judgments.json');a.out_dir.mkdir(parents=True,exist_ok=True)
 (a.out_dir/'creator-pool-table.md').write_text(pool_report(result));(a.out_dir/'round2-quality.md').write_text(quality(result,usage,j2));(a.out_dir/'round-compare.md').write_text(compare(r1,result,j1,j2))
if __name__=='__main__':main()
