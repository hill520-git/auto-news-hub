#!/usr/bin/env python3
"""
每日热点抓取脚本
- 抓取知乎热榜 TOP 20
- 抓取微博热搜 TOP 20
- 更新 index.html 和 data/trends.json
"""

import requests
import json
import re
import os
from datetime import datetime


def fetch_zhihu():
    """抓取知乎热榜"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
        }
        resp = requests.get(
            'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=30',
            headers=headers,
            timeout=20
        )
        data = resp.json()
        items = []
        for item in data.get('data', [])[:20]:
            target = item.get('target', {})
            title = target.get('title', '')
            url = target.get('url', '')
            if url and not url.startswith('http'):
                url = 'https://www.zhihu.com' + url
            heat = item.get('detail_text', item.get('metrics', ''))
            items.append({
                'title': title,
                'url': url or f"https://www.zhihu.com/search?q={title}",
                'heat': heat
            })
        return items
    except Exception as e:
        print(f"[WARN] 知乎抓取失败: {e}")
        return []


def fetch_weibo():
    """抓取微博热搜"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://weibo.com/',
        }
        resp = requests.get(
            'https://weibo.com/ajax/side/hotSearch',
            headers=headers,
            timeout=20
        )
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('realtime', [])[:20]:
            word = item.get('word', '')
            raw_hot = item.get('raw_hot', 0)
            items.append({
                'title': word,
                'url': f"https://s.weibo.com/weibo?q={word}",
                'heat': f"热度 {raw_hot}"
            })
        return items
    except Exception as e:
        print(f"[WARN] 微博抓取失败: {e}")
        return []


def update_index(zhihu, weibo):
    """更新 index.html 中的热点列表"""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("[WARN] index.html 不存在，跳过更新")
        return

    # 生成知乎热榜 HTML
    if zhihu:
        zhihu_html = '\n'.join([
            f'      <li><span class="badge badge-zhihu">知乎</span><a href="{x["url"]}" target="_blank">{x["title"]}</a><span class="heat">{x["heat"]}</span></li>'
            for x in zhihu
        ])
    else:
        zhihu_html = '      <li style="color:#999;">今日知乎数据暂不可用，请稍后刷新</li>'

    # 生成微博热搜 HTML
    if weibo:
        weibo_html = '\n'.join([
            f'      <li><span class="badge badge-weibo">微博</span><a href="{x["url"]}" target="_blank">{x["title"]}</a><span class="heat">{x["heat"]}</span></li>'
            for x in weibo
        ])
    else:
        weibo_html = '      <li style="color:#999;">今日微博数据暂不可用，请稍后刷新</li>'

    # 替换占位符
    content = re.sub(
        r'<!-- ZHIHU_START -->.*?<!-- ZHIHU_END -->',
        f'<!-- ZHIHU_START -->\n{zhihu_html}\n      <!-- ZHIHU_END -->',
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r'<!-- WEIBO_START -->.*?<!-- WEIBO_END -->',
        f'<!-- WEIBO_START -->\n{weibo_html}\n      <!-- WEIBO_END -->',
        content,
        flags=re.DOTALL
    )

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

    print("[OK] index.html 已更新")


def generate_articles_index():
    """扫描 articles 目录，生成文章索引"""
    articles = []
    articles_dir = 'articles'
    if not os.path.exists(articles_dir):
        return

    for fname in sorted(os.listdir(articles_dir), reverse=True):
        if not fname.endswith('.md') or fname == 'template.md' or fname == 'README.md':
            continue
        fpath = os.path.join(articles_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        title = fname.replace('.md', '')
        # 尝试从第一行提取标题
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('# '):
                title = line[2:].strip()
                break
        date = fname[:10] if len(fname) > 10 else ''
        read_time = max(1, len(lines) // 40)
        articles.append({
            'title': title,
            'file': fname,
            'date': date,
            'readTime': read_time
        })

    index_path = os.path.join(articles_dir, 'index.json')
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"[OK] 文章索引已更新，共 {len(articles)} 篇")


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取热点...")

    os.makedirs('data', exist_ok=True)

    zhihu = fetch_zhihu()
    weibo = fetch_weibo()

    trends = {
        'date': datetime.now().isoformat(),
        'zhihu': zhihu,
        'weibo': weibo
    }

    with open('data/trends.json', 'w', encoding='utf-8') as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)

    print(f"[OK] 知乎: {len(zhihu)} 条, 微博: {len(weibo)} 条")

    update_index(zhihu, weibo)
    generate_articles_index()

    print("[OK] 全部完成")


if __name__ == '__main__':
    main()
