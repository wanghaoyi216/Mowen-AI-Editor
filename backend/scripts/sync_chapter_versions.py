"""Sync ChapterVersion.content with Chapter.final_content.

Root cause: seed_full_demo.py rewrote Chapter.final_content but did not
update existing ChapterVersion rows. Frontend Tab3 reads version.content
(first), so it still shows the old 443-word outline-style content.

Strategy:
  1. For every ChapterVersion, if its chapter has final_content AND
     (version content is missing/short), copy chapter.final_content
     into version.content.
  2. Recompute version.word_count accordingly.
  3. Print a summary so we can verify.
"""
import sys

# Allow running from inside the container
sys.path.insert(0, "/app")

from app.db.base import SessionLocal
from app.db.models import Chapter, ChapterVersion


def main() -> int:
    db = SessionLocal()
    try:
        versions = db.query(ChapterVersion).all()
        total = len(versions)
        updated = 0
        skipped = 0
        no_chapter = 0

        for v in versions:
            ch = db.get(Chapter, v.chapter_id)
            if ch is None:
                no_chapter += 1
                continue
            if not ch.final_content:
                skipped += 1
                continue
            v_len = len(v.content or "")
            ch_len = len(ch.final_content)
            # update when version content is missing or noticeably shorter
            if v_len < ch_len - 50:
                v.content = ch.final_content
                v.word_count = ch.word_count or ch_len
                updated += 1
            else:
                skipped += 1

        db.commit()

        print(f"Total versions: {total}")
        print(f"Updated:        {updated}")
        print(f"Skipped:        {skipped}")
        print(f"No chapter:     {no_chapter}")
        print("--- per-chapter sample ---")
        for v in db.query(ChapterVersion).limit(8).all():
            ch = db.get(Chapter, v.chapter_id)
            print(
                f"  v{v.version_number} ch{v.chapter_id} "
                f"len={len(v.content or '')} wc={v.word_count} "
                f"title={(ch.title if ch else '?')[:20]}"
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
