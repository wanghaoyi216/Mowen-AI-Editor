"""
补拍 2 张主题截图：
- 10-theme-mowen-default.png (墨问·默认)
- 21-theme-vermilion.png   (秋枫·霞谷)

逻辑：admin 登录 → 选项目 → 打开主题面板 → 切主题 → 截图 → 关闭面板
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\Study\novel_ai_editer\docs\screenshots")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://localhost:8080"


def shot(page, name):
    p = OUT_DIR / name
    page.screenshot(path=str(p), full_page=True)
    print(f"  📸 {name} ({p.stat().st_size // 1024} KB)")


def open_theme_panel(page):
    """打开主题切换器面板"""
    page.locator('button[aria-label*="主题"]').first.click()
    page.wait_for_timeout(1500)


def close_theme_panel(page):
    """点遮罩关闭面板"""
    page.mouse.click(400, 500)
    page.wait_for_timeout(1200)


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
        page.set_default_timeout(20000)

        # 1. 登录
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.locator('input[autocomplete="username"]').fill("admin")
        page.locator('input[autocomplete="current-password"]').fill("admin123456")
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(3000)
        print(f"[1] 登录 OK, URL: {page.url}")

        # 2. 选项目
        sel = page.locator('select').first
        sel.wait_for(state="visible", timeout=10000)
        sel.select_option(value="1")
        page.wait_for_timeout(4000)
        print(f"[2] 选项目 OK, URL: {page.url}")

        # 3. 切到 秋枫·霞谷 (vermilion) 先
        print("\n[3] 切到秋枫·霞谷")
        open_theme_panel(page)
        try:
            page.locator('.cc-theme-card:has-text("秋枫")').first.click()
            page.wait_for_timeout(2500)
            shot(page, "21-theme-vermilion.png")
            close_theme_panel(page)
        except Exception as e:
            print(f"  失败: {e}")
            # 用 JS 直接点
            page.evaluate("""
                const cards = document.querySelectorAll('.cc-theme-card');
                for (const c of cards) {
                    if (c.textContent.includes('秋枫')) { c.click(); break; }
                }
            """)
            page.wait_for_timeout(2500)
            shot(page, "21-theme-vermilion.png")
            close_theme_panel(page)

        # 4. 切回 墨问·默认
        print("\n[4] 切回墨问·默认")
        open_theme_panel(page)
        try:
            page.locator('.cc-theme-card:has-text("墨问·默认")').first.click()
            page.wait_for_timeout(2500)
            shot(page, "10-theme-mowen-default.png")
            close_theme_panel(page)
        except Exception as e:
            print(f"  失败: {e}")
            page.evaluate("""
                const cards = document.querySelectorAll('.cc-theme-card');
                for (const c of cards) {
                    if (c.textContent.includes('墨问·默认')) { c.click(); break; }
                }
            """)
            page.wait_for_timeout(2500)
            shot(page, "10-theme-mowen-default.png")
            close_theme_panel(page)

        browser.close()
    print("\n✅ 主题补拍完成")


if __name__ == "__main__":
    main()
