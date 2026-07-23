#!/usr/bin/env python3
"""
多平台热点聚合抓取脚本 v2
- 知乎热榜（多端点 fallback）
- 微博热搜
- 百度热搜
- B站热榜
- 输出：index.html + data/trends.json

新增平台只需在 PLATFORMS 字典里加一行，网页自动更新。
"""

import requests
import json
import re
import os
from datetime import datetime

###############################################################################
#  平台抓取函数 —— 每个平台一个独立 fetch 函数，返回 [{title, url, heat}]  #
###############################################################################

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


def fetch_zhihu():
    """知乎热榜 —— 主端点 + 备用端点，多个全试"""
    endpoints = [
        'https://www.zhihu.com/api/v4/search/top_search',
        'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=30',
        'https://www.zhihu.com/zhihu-rn/api/v4/search/top_search',
    ]
    headers = {**HEADERS, 'Referer': 'https://www.zhihu.com/'}

    for ep in endpoints:
        try:
            resp = requests.get(ep, headers=headers, timeout=15)
            data = resp.json()

            # 端点1：top_search
            if 'top_search' in ep:
                items = []
                for w in data.get('top_search', {}).get('words', [])[:20]:
                    query = w.get('query', '')
                    items.append({
                        'title': query,
                        'url': f'https://www.zhihu.com/search?q={query}',
                        'heat': f"热度 {w.get('display_query', '')}"
                    })
                if items:
                    return items

            # 端点2：hot-lists/total
            records = data.get('data', [])
            items = []
            for item in records[:20]:
                target = item.get('target', {})
                title = target.get('title', '') or target.get('excerpt', '')
                url = target.get('url', '')
                if url and not url.startswith('http'):
                    url = 'https://www.zhihu.com' + url
                heat = item.get('detail_text', item.get('metrics', ''))
                items.append({
                    'title': title,
                    'url': url or f'https://www.zhihu.com/search?q={title}',
                    'heat': str(heat) if heat else ''
                })
            if items:
                return items
        except Exception:
            continue

    return []


def fetch_weibo():
    """微博热搜"""
    headers = {**HEADERS, 'Referer': 'https://weibo.com/'}
    try:
        resp = requests.get(
            'https://weibo.com/ajax/side/hotSearch',
            headers=headers, timeout=15
        )
        data = resp.json()
        return [
            {
                'title': item.get('word', '').replace('#', ''),
                'url': f'https://s.weibo.com/weibo?q={item.get("word", "").replace("#", "")}',
                'heat': f"🔥 {item.get('raw_hot', 0)}"
            }
            for item in data.get('data', {}).get('realtime', [])[:20]
        ]
    except Exception:
        return []


def fetch_baidu():
    """百度实时热搜  —— 使用官方 JSON API"""
    headers = {**HEADERS, 'Referer': 'https://top.baidu.com/'}
    try:
        resp = requests.get(
            'https://top.baidu.com/api/board?tab=realtime',
            headers=headers, timeout=15
        )
        data = resp.json()
        items = []
        for card in data.get('data', {}).get('cards', []):
            for c in card.get('content', []):
                word = c.get('word', '') or c.get('query', '')
                url = c.get('url', '') or c.get('appUrl', '') or f'https://www.baidu.com/s?wd={word}'
                if word and len(items) < 20:
                    items.append({'title': word, 'url': url, 'heat': f'🔥 {c.get("hotScore", c.get("desc", ""))}'})
        return items
    except Exception:
        return []


def fetch_bilibili():
    """B站全站热门榜"""
    try:
        resp = requests.get(
            'https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all',
            headers=HEADERS, timeout=15
        )
        data = resp.json()
        return [
            {
                'title': v.get('title', ''),
                'url': f'https://www.bilibili.com/video/{v.get("bvid", "")}',
                'heat': f"播放 {_fmt_num(v.get('play', 0))}"
            }
            for v in data.get('data', {}).get('list', [])[:20]
        ]
    except Exception:
        return []


def fetch_toutiao():
    """今日头条热榜 —— 官方 JSON 接口，免费无需 Key"""
    headers = {**HEADERS, 'Referer': 'https://www.toutiao.com/'}
    try:
        resp = requests.get(
            'https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc',
            headers=headers, timeout=15
        )
        data = resp.json()
        return [
            {
                'title': item.get('Title', ''),
                'url': item.get('Url', '') or f'https://www.toutiao.com/trending/{item.get("ClusterId", "")}',
                'heat': f'🔥 {_fmt_num(item.get("HotValue", ""))}' if item.get('HotValue') else ''
            }
            for item in data.get('data', [])[:20]
        ]
    except Exception:
        return []


def fetch_netease():
    """网易新闻热榜 —— 官方移动端 API"""
    headers = {**HEADERS, 'Referer': 'https://m.163.com/'}
    try:
        resp = requests.get(
            'https://m.163.com/fe/api/hot/news/flow',
            headers=headers, timeout=15
        )
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('list', [])[:20]:
            title = item.get('title', '')
            skip_id = item.get('skipID', '')
            items.append({
                'title': title,
                'url': f'https://www.163.com/dy/article/{skip_id}.html' if skip_id else item.get('url', ''),
                'heat': item.get('rank', '')
            })
        return items
    except Exception:
        return []


###############################################################################
#  平台注册表 —— 要加新平台，在这里加一条就行                           #
###############################################################################
PLATFORMS = {
    'zhihu':    {'name': '📰 知乎热榜', 'label': '知乎',   'badge': 'badge-zhihu',    'fetch': fetch_zhihu},
    'weibo':    {'name': '🔥 微博热搜', 'label': '微博',   'badge': 'badge-weibo',    'fetch': fetch_weibo},
    'baidu':    {'name': '🔍 百度热搜', 'label': '百度',   'badge': 'badge-baidu',    'fetch': fetch_baidu},
    'bilibili': {'name': '🎬 B站热榜',  'label': 'B站',    'badge': 'badge-bilibili', 'fetch': fetch_bilibili},
    'toutiao':  {'name': '📱 头条热榜', 'label': '头条',   'badge': 'badge-toutiao',  'fetch': fetch_toutiao},
    'netease':  {'name': '📡 网易热榜', 'label': '网易',   'badge': 'badge-netease',  'fetch': fetch_netease},
}


###############################################################################
#  工具函数                                                                   #
###############################################################################

def _fmt_num(n):
    try:
        n = int(n)
    except Exception:
        pass
    if isinstance(n, (int, float)) and n >= 10000:
        return f'{n / 10000:.1f}万'
    return str(n)


def _make_section_html(key, cfg, items):
    badge = cfg['badge']
    label = cfg['label']
    if not items:
        return f'<li style="color:#999;">今日{cfg["name"][:2]}数据暂不可用，请稍后刷新</li>'

    lines = []
    for x in items:
        heat = x.get('heat', '')
        heat_html = f'<span class="heat">{heat}</span>' if heat else ''
        lines.append(
            f'      <li><span class="badge {badge}">{label}</span>'
            f'<a href="{x["url"]}" target="_blank">{x["title"]}</a>'
            f'{heat_html}</li>'
        )
    return '\n'.join(lines)


###############################################################################
#  更新 index.html                                                            #
###############################################################################

def update_index(platform_data):
    """扫描 index.html 中的 <!-- KEY_START --> 标记，自动替换各平台热榜。"""

    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    for key, cfg in PLATFORMS.items():
        items = platform_data.get(key, [])
        html = _make_section_html(key, cfg, items)
        marker_start = f'<!-- {key.upper()}_START -->'
        marker_end   = f'<!-- {key.upper()}_END -->'
        pattern = re.compile(
            re.escape(marker_start) + r'.*?' + re.escape(marker_end),
            re.DOTALL
        )
        replacement = f'{marker_start}\n{html}\n      {marker_end}'
        content = pattern.sub(replacement, content)
        print(f'  [{key}] {len(items)} 条')

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print('[OK] index.html 已更新')


def generate_articles_index():
    """扫描 articles 目录生成文章索引。"""
    articles = []
    articles_dir = 'articles'
    if not os.path.exists(articles_dir):
        return

    for fname in sorted(os.listdir(articles_dir), reverse=True):
        if not fname.endswith('.md') or fname in ('template.md', 'README.md'):
            continue
        fpath = os.path.join(articles_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        title = fname.replace('.md', '')
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('# '):
                title = line[2:].strip()
                break
        date = fname[:10] if len(fname) > 10 else ''
        articles.append({
            'title': title,
            'file': fname,
            'date': date,
            'readTime': max(1, len(lines) // 40)
        })

    os.makedirs(articles_dir, exist_ok=True)
    with open(os.path.join(articles_dir, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f'[OK] 文章索引已更新，共 {len(articles)} 篇')


def main():
    os.makedirs('data', exist_ok=True)

    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] 开始抓取多平台热点...')

    total_items = {}
    for key, cfg in PLATFORMS.items():
        print(f'  抓取 {cfg["name"]}... ', end='', flush=True)
        items = cfg['fetch']()
        total_items[key] = items
        print(f'{len(items)} 条')

    # 写入 trends.json
    trends = {'date': datetime.now().isoformat(), **total_items}

    with open('data/trends.json', 'w', encoding='utf-8') as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)

    update_index(total_items)
    generate_articles_index()

    total = sum(len(v) for v in total_items.values())
    print(f'\n[OK] 全部完成！共 {total} 条热点')


if __name__ == '__main__':
    main()
