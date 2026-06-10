"""
补拍 10 墨问·默认 + 20 AI 聊天
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

        # 注册
        print("\n[注册]")
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

        # 10 墨问·默认（注册后默认就是墨问·默认主题）
        print("\n[10] 墨问·默认主题（注册后默认）")
        page.wait_for_timeout(2000)
        shot(page, "10-theme-mowen-default.png")

        # 20 AI 聊天
        print("\n[20] AI 聊天面板")
        # 展开 AI 聊天 - 点 sidebar 内的项目图标区
        # 实际上 sidebar 默认就是展开的（看 21 的截图），找 textarea
        try:
            ai_input = page.locator('textarea').first
            ai_input.click()
            ai_input.fill("请给我推荐一个玄幻小说的开篇，需要有张力的第一段")
            page.wait_for_timeout(800)
            shot(page, "20-agent-chat-input.png")
        except Exception as e:
            print(f"   失败: {e}")
            # 看 page 内容
            html = page.content()
            Path("D:/tmp/agent_chat_debug.html").write_text(html[:50000], encoding="utf-8")
            print("   HTML saved to D:/tmp/agent_chat_debug.html")

        browser.close()
    print("\n✅ 完成")

if __name__ == "__main__":
    main()
