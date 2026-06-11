"""
以 admin 登录，进入项目 "趁青春，奋斗去！"(id=1, 30 章节),
逐 Tab 截图，**先看效果再决定是否要重拍**
"""
import time
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\Study\novel_ai_editer\docs\screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123456"

# 只清掉上一轮的 PNG（01-19 + 21），保留 theme-XX
print("[*] 清掉旧截图")
for p in OUT_DIR.glob("*.png"):
    n = p.name
    if not n.startswith("theme-"):
        p.unlink()


def shot(page, name, full=True):
    p = OUT_DIR / name
    page.screenshot(path=str(p), full_page=full)
    print(f"  📸 {name} ({p.stat().st_size // 1024} KB)")
    return p


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=EDGE,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                  "--hide-scrollbars", "--window-size=1920,1080"],
        )
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        page = ctx.new_page()
        page.set_default_timeout(15000)

        # ============================================================
        # 1. 登录
        # ============================================================
        print("\n[1] 登录 admin")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.locator('input[autocomplete="username"]').fill(ADMIN_USER)
        page.locator('input[autocomplete="current-password"]').fill(ADMIN_PASS)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(3000)
        print(f"   URL: {page.url}")

        # ============================================================
        # 2. 在 <select> 下拉里选 "趁青春，奋斗去！" (id=1)
        # ============================================================
        print("\n[2] 在项目下拉里选中 id=1（趁青春，奋斗去！）")
        try:
            # 等待 select 渲染
            sel = page.locator('select').first
            sel.wait_for(state="visible", timeout=10000)
            sel.select_option(value="1")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(4000)  # 给图表/数据时间渲染
            print(f"   URL: {page.url}")
        except Exception as e:
            print(f"   选项目失败: {e}")
            html = page.content()
            Path("D:/tmp/debug_home.html").write_text(html[:30000], encoding="utf-8")
            print("   → 写了 D:/tmp/debug_home.html")
            browser.close()
            return

        # ============================================================
        # 3. 主页（项目详情 + 默认 Tab = 故事总览）
        # ============================================================
        print("\n[3] 主页-故事总览 Tab")
        shot(page, "04-home-project.png")

        # ============================================================
        # 4. 8 个 Tab 依次截图
        # ============================================================
        tabs = [
            ("热点探索", "12-tab-热点探索.png"),
            ("世界构建", "13-tab-世界构建.png"),
            ("章节写作", "14-tab-章节写作.png"),
            ("一致性检查", "15-tab-一致性检查.png"),
            ("故事图谱", "16-tab-故事图谱.png"),
            ("故事脉络", "17-tab-故事脉络.png"),
            ("全局统计", "18-tab-全局统计.png"),
            ("故事总览", "19-tab-故事总览.png"),
        ]
        for tab_text, fname in tabs:
            try:
                print(f"\n  -> Tab: {tab_text}")
                page.locator(f'button.cc-tab:has-text("{tab_text}")').first.click()
                page.wait_for_timeout(3500)  # 给图表渲染时间
                shot(page, fname)
            except Exception as e:
                print(f"   跳过: {e}")

        # ============================================================
        # 5. 主题切换 - 宁静·远景
        # ============================================================
        print("\n[5] 切到宁静·远景主题")
        try:
            page.locator('button[aria-label*="主题"]').first.click()
            page.wait_for_timeout(800)
            page.locator('.cc-theme-card:has-text("宁静")').first.click()
            page.wait_for_timeout(1500)
            shot(page, "09-theme-cyan-jade.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 6. 主题切换 - 秋枫·霞谷
        # ============================================================
        print("\n[6] 切到秋枫·霞谷主题")
        try:
            page.locator('button[aria-label*="主题"]').first.click()
            page.wait_for_timeout(800)
            page.locator('.cc-theme-card:has-text("秋枫")').first.click()
            page.wait_for_timeout(1500)
            shot(page, "21-theme-vermilion.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 7. 切回墨问·默认
        # ============================================================
        print("\n[7] 切回墨问·默认")
        try:
            page.locator('button[aria-label*="主题"]').first.click()
            page.wait_for_timeout(800)
            page.locator('.cc-theme-card:has-text("墨问·默认")').first.click()
            page.wait_for_timeout(1500)
            shot(page, "10-theme-mowen-default.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 8. 主题切换面板（完整 6 张）
        # ============================================================
        print("\n[8] 主题切换面板")
        try:
            page.locator('button[aria-label*="主题"]').first.click()
            page.wait_for_timeout(1000)
            shot(page, "08-theme-switcher.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        browser.close()
    print("\n✅ 全部截图完成")


if __name__ == "__main__":
    main()
