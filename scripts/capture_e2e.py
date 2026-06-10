"""
用 Playwright + 系统 Edge 一步步截图：
  登录页 → 注册 tab → 填表 → 注册成功 → 主页 → 新建项目 → 启动创作 → 主题切换 → 各 Tab
"""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT_DIR = Path(r"D:\Study\novel_ai_editer\docs\screenshots")
OUT_DIR.mkdir(parents=True, exist_ok=True)
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
BASE = "http://localhost:8080"

# 清空旧截图
for p in OUT_DIR.glob("*.png"):
    p.unlink()

USERNAME = f"demo{int(time.time()) % 100000}"
PASSWORD = "demo123456"
EMAIL = f"{USERNAME}@mowen.ai"
DISPLAY = "演示账号"

print(f"使用账号: {USERNAME}")


def shot(page, name, full=True):
    p = OUT_DIR / name
    page.screenshot(path=str(p), full_page=full)
    print(f"  📸 {name} ({p.stat().st_size // 1024} KB)")


def close_modal(page):
    """关掉模态弹窗（.cc-modal-backdrop 内的 .cc-btn-close 按钮）"""
    try:
        if page.locator(".cc-modal-backdrop").is_visible(timeout=500):
            page.locator(".cc-btn-close").first.click(timeout=2000)
            page.wait_for_timeout(600)
            return True
    except Exception:
        pass
    return False


def click_outside_theme_panel(page):
    """点击主内容区空白处关闭主题 panel（panel 在右上角）"""
    page.mouse.click(400, 500)  # 主内容区中偏左
    page.wait_for_timeout(600)


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=EDGE,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--hide-scrollbars",
                "--window-size=1920,1080",
            ],
        )
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-CN")
        page = ctx.new_page()
        page.set_default_timeout(15000)

        # ============================================================
        # 1. 登录页
        # ============================================================
        print("\n[1] 打开登录页")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.wait_for_timeout(1500)
        shot(page, "01-login.png")

        # ============================================================
        # 2. 切换到"注册" tab
        # ============================================================
        print("\n[2] 切换到注册 tab")
        page.locator(".login-tab", has_text="注 册").first.click()
        page.wait_for_timeout(800)
        shot(page, "02-register-tab.png")

        # ============================================================
        # 3. 填表注册
        # ============================================================
        print("\n[3] 填写注册信息")
        page.locator('input[autocomplete="username"]').fill(USERNAME)
        page.locator('input[autocomplete="new-password"]').fill(PASSWORD)
        page.locator('input[autocomplete="email"]').fill(EMAIL)
        page.locator('input[placeholder="默认与用户名一致"]').fill(DISPLAY)
        page.wait_for_timeout(500)
        shot(page, "03-register-filled.png")

        # ============================================================
        # 4. 提交注册
        # ============================================================
        print("\n[4] 提交注册")
        with page.expect_navigation(timeout=15000, wait_until="networkidle"):
            page.locator('button:has-text("注册并登录")').click()
        page.wait_for_timeout(2000)
        print(f"   当前 URL: {page.url}")
        shot(page, "04-home-after-register.png")

        # ============================================================
        # 5. 打开新建项目弹窗
        # ============================================================
        print("\n[5] 打开新建项目弹窗")
        try:
            page.locator('button:has-text("新建")').first.click(timeout=3000)
            page.wait_for_timeout(1000)
            shot(page, "05-new-project-modal.png")
            # 填写项目名
            try:
                page.locator('input[placeholder*="为你的小说"]').fill("九州·长歌行")
                page.locator('input[placeholder*="例如"]').fill("少年 江湖 宿命 成长")
                page.wait_for_timeout(500)
                shot(page, "06-new-project-filled.png")
            except Exception as e:
                print(f"   填表跳过: {e}")
            # 点确认创建
            try:
                page.locator('button:has-text("确认创建")').click(timeout=3000)
                page.wait_for_timeout(4000)
                shot(page, "07-after-create-project.png")
            except Exception as e:
                print(f"   确认创建跳过: {e}")
                close_modal(page)
        except Exception as e:
            print(f"   跳过: {e}")
            close_modal(page)

        # ============================================================
        # 8. 主题切换面板
        # ============================================================
        print("\n[8] 打开主题切换面板")
        page.locator('button[aria-label*="主题"]').first.click()
        page.wait_for_timeout(1000)
        shot(page, "08-theme-switcher.png")

        # ============================================================
        # 9. 切换到"宁静·远景"主题
        # ============================================================
        print("\n[9] 切换到宁静·远景主题")
        try:
            page.locator('.cc-theme-card:has-text("宁静")').first.click(timeout=3000)
            page.wait_for_timeout(1500)
            shot(page, "09-theme-cyan-jade.png")
            # 关闭 panel
            click_outside_theme_panel(page)
        except Exception as e:
            print(f"   跳过: {e}")

        # ============================================================
        # 10. 切回墨问·默认主题
        # ============================================================
        print("\n[10] 切回墨问·默认主题")
        try:
            page.locator('button[aria-label*="主题"]').first.click(timeout=3000)
            page.wait_for_timeout(800)
            page.locator('.cc-theme-card:has-text("墨问·默认")').first.click(timeout=3000)
            page.wait_for_timeout(1500)
            shot(page, "10-theme-mowen-default.png")
            click_outside_theme_panel(page)
        except Exception as e:
            print(f"   跳过: {e}")
            click_outside_theme_panel(page)

        # ============================================================
        # 11. 启动 AI 创作弹窗
        # ============================================================
        print("\n[11] 启动 AI 创作弹窗")
        try:
            page.locator('button:has-text("启动 AI 创作")').first.click(timeout=3000)
            page.wait_for_timeout(1500)
            shot(page, "11-start-creation-modal.png")
            close_modal(page)
        except Exception as e:
            print(f"   跳过: {e}")
            close_modal(page)

        # ============================================================
        # 12-19. 各个 Tab
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
                page.locator(f'button.cc-tab:has-text("{tab_text}")').first.click(timeout=5000)
                page.wait_for_timeout(2500)
                shot(page, fname)
            except Exception as e:
                print(f"   跳过: {e}")

        # ============================================================
        # 20. AI 聊天面板
        # ============================================================
        print("\n[20] AI 聊天面板")
        try:
            # 先切回故事总览
            page.locator('button.cc-tab:has-text("故事总览")').first.click(timeout=5000)
            page.wait_for_timeout(1000)
            ai_input = page.locator('textarea[placeholder*="给 AI"]').first
            ai_input.click()
            ai_input.fill("请给我推荐一个玄幻小说的开篇")
            page.wait_for_timeout(1000)
            shot(page, "20-agent-chat-input.png")
        except Exception as e:
            print(f"   跳过: {e}")

        browser.close()
    print("\n✅ 全部截图完成")
    print(f"\n文件列表:")
    for p in sorted(OUT_DIR.glob("*.png")):
        print(f"  {p.name} - {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
