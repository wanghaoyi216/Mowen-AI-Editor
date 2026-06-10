"""清空 Neo4j 中所有节点和关系。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from neo4j import GraphDatabase

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清空 Neo4j 中所有节点和关系。")
    parser.add_argument("--force", action="store_true", help="跳过交互确认，直接执行清理。")
    return parser.parse_args()


def confirm_or_exit(force: bool) -> None:
    print("警告：即将清空 Neo4j 中所有节点和关系。")
    print("执行语句：MATCH (n) DETACH DELETE n")

    if force:
        print("已使用 --force，跳过交互确认。")
        return

    answer = input("请输入 CLEAN 确认执行清理：").strip()
    if answer != "CLEAN":
        print("未确认，已取消清理。")
        raise SystemExit(0)


def clean_neo4j() -> tuple[int, int]:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        with driver.session(database=settings.neo4j_database) as session:
            counts = session.run(
                """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]-()
                RETURN count(DISTINCT n) AS node_count, count(DISTINCT r) AS relationship_count
                """
            ).single()
            node_count = int(counts["node_count"]) if counts is not None else 0
            relationship_count = int(counts["relationship_count"]) if counts is not None else 0
            session.run("MATCH (n) DETACH DELETE n").consume()
            return node_count, relationship_count
    except Exception as exc:
        print(f"Neo4j 清理失败：{exc}", file=sys.stderr)
        raise
    finally:
        driver.close()


def main() -> int:
    args = parse_args()
    confirm_or_exit(args.force)

    print(f"Neo4j 连接：{settings.neo4j_uri} / database={settings.neo4j_database}")
    try:
        node_count, relationship_count = clean_neo4j()
    except Exception:
        return 1

    print(f"Neo4j 清理完成：清理 {node_count} 个节点，{relationship_count} 条关系。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
