"""
补拍 2 张截图：墨问·默认主题 + 展开 AI 聊天面板
完整重做：注册 → 进入项目 → 切回墨问·默认 → 展开 AI 聊天
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\Study\novel_ai_editer\docs\screenshots")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://localhost:8080"

USERNAME = f"demo{int(time.time()) % 100000}"
PASSWORD = "demo123456"
EMAIL = f"{USERNAME}@mowen.ai"
DISPLAY = "演示账号"
print(f"账号: {USERNAME}")

def shot(page, name):
    p = OUT_DIR / name
    page.screenshot(path=str(p), full_page=True)
    print(f"  📸 {name} ({p.stat().st_size // 1024} KB)")

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=EDGE,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars", "--window-size=1920,1080"],
        )
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        page = ctx.new_page()
        page.set_default_timeout(15000)

        # ============================================================
        # 1. 注册新账号
        # ============================================================
        print("\n[1] 注册")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.locator(".login-tab", has_text="注 册").first.click()
        page.wait_for_timeout(500)
        page.locator('input[autocomplete="username"]').fill(USERNAME)
        page.locator('input[autocomplete="new-password"]').fill(PASSWORD)
        page.locator('input[autocomplete="email"]').fill(EMAIL)
        page.locator('input[placeholder="默认与用户名一致"]').fill(DISPLAY)
        page.locator('button:has-text("注册并登录")').click()
        page.wait_for_timeout(3000)
        print(f"   URL: {page.url}")

        # ============================================================
        # 2. 创建项目
        # ============================================================
        print("\n[2] 创建项目")
        try:
            page.locator('button:has-text("新建")').first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.locator('input[placeholder*="为你的小说"]').fill("九州·长歌行")
            page.locator('input[placeholder*="例如"]').fill("少年 江湖 宿命 成长")
            page.locator('button:has-text("确认创建")').click(timeout=5000)
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 3. 切到墨问·默认主题
        # ============================================================
        print("\n[3] 切到墨问·默认主题")
        try:
            page.locator('button[aria-label*="主题"]').first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.locator('.cc-theme-card:has-text("墨问·默认")').first.click(timeout=5000)
            page.wait_for_timeout(1500)
            shot(page, "10-theme-mowen-default.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 4. 切到宁静·远景主题（用于对比）
        # ============================================================
        print("\n[4] 切到宁静·远景")
        try:
            page.locator('button[aria-label*="主题"]').first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.locator('.cc-theme-card:has-text("宁静")').first.click(timeout=5000)
            page.wait_for_timeout(1500)
            shot(page, "09-theme-cyan-jade.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 5. 切到秋枫·霞谷（朱砂红）
        # ============================================================
        print("\n[5] 切到秋枫·霞谷")
        try:
            page.locator('button[aria-label*="主题"]').first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.locator('.cc-theme-card:has-text("秋枫")').first.click(timeout=5000)
            page.wait_for_timeout(1500)
            shot(page, "21-theme-vermilion.png")
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 6. 切回墨问·默认
        # ============================================================
        print("\n[6] 切回墨问·默认")
        try:
            page.locator('button[aria-label*="主题"]').first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.locator('.cc-theme-card:has-text("墨问·默认")').first.click(timeout=5000)
            page.wait_for_timeout(1500)
            page.mouse.click(400, 500)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 7. 展开 AI 聊天面板
        # ============================================================
        print("\n[7] 展开 AI 聊天面板")
        try:
            # 点击 sidebar toggle 按钮展开
            toggle = page.locator('.chat-sidebar-toggle').first
            if toggle.is_visible(timeout=2000):
                toggle.click()
                page.wait_for_timeout(1000)
        except Exception as e:
            print(f"   toggle 失败: {e}")

        # 在 AI 输入框填内容
        try:
            ai_input = page.locator('textarea[placeholder*="给 AI"]').first
            ai_input.click()
            ai_input.fill("请给我推荐一个玄幻小说的开篇，需要有张力的第一段")
            page.wait_for_timeout(800)
            shot(page, "20-agent-chat-input.png")
        except Exception as e:
            print(f"   AI 聊天输入失败: {e}")
            try:
                ai_input = page.locator('textarea').first
                ai_input.click()
                ai_input.fill("请给我推荐一个玄幻小说的开篇")
                page.wait_for_timeout(800)
                shot(page, "20-agent-chat-input.png")
            except Exception as e2:
                print(f"   fallback 也失败: {e2}")

        browser.close()
    print("\n✅ 完成")

if __name__ == "__main__":
    main()
