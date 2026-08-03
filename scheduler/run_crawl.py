"""命令行抓取入口：手动运行或加入 cron / launchd 定时执行。

示例：
  python scheduler/run_crawl.py                 # 抓取全部开启源，近 7 天
  python scheduler/run_crawl.py --days 7        # 显式指定天数
  python scheduler/run_crawl.py --sources sina_sports netease_sports
  python scheduler/run_crawl.py --no-comments   # 不抓评论
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers import registry  # noqa: E402


def main():
    p = argparse.ArgumentParser(description="体育新闻抓取")
    p.add_argument("--days", type=int, default=7, help="抓取最近 N 天")
    p.add_argument("--sources", nargs="*", default=None, help="限定源 id（默认全部开启源）")
    p.add_argument("--no-comments", action="store_true", help="跳过评论抓取")
    args = p.parse_args()

    registry.run_crawl(days=args.days, source_ids=args.sources,
                       with_comments=not args.no_comments)
    print("抓取完成。")


if __name__ == "__main__":
    main()
