"""端到端验证主题切换功能
- 打开登录页，截图初始状态
- 直接访问 / 路由（未登录会被重定向到 /login，但能看到主题切换效果）
- 用 localStorage 注入 currentId 模拟主题切换
- 检查 --theme-primary / --theme-bg-image 是否更新
"""
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    # 初始状态：登录页
    page.screenshot(path="/tmp/theme-1-login-initial.png", full_page=False)
    print("[1] initial state captured")

    # 检查 :root 上 --theme-primary 默认值
    initial_primary = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--theme-primary')")
    initial_bg_img = page.evaluate("getComputedStyle(document.querySelector('.login-page')).getPropertyValue('--theme-bg-image')")
    print(f"[2] initial --theme-primary = {initial_primary.strip()!r}")
    print(f"[3] initial --theme-bg-image = {initial_bg_img.strip()[:80]!r}")

    # 用 localStorage 强制切到秋枫霞谷
    page.evaluate("""
        localStorage.setItem('novel-ai.theme.v1', JSON.stringify({
            currentId: 'vermilion-maple',
            custom: []
        }));
    """)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/theme-2-vermilion.png", full_page=False)
    print("[4] vermilion-maple theme captured")

    vermilion_primary = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--theme-primary')")
    vermilion_bg = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--theme-bg')")
    print(f"[5] vermilion --theme-primary = {vermilion_primary.strip()!r}")
    print(f"[6] vermilion --theme-bg = {vermilion_bg.strip()!r}")

    # 切到 cyan-jade
    page.evaluate("""
        localStorage.setItem('novel-ai.theme.v1', JSON.stringify({
            currentId: 'cyan-jade',
            custom: []
        }));
    """)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/theme-3-cyan.png", full_page=False)
    print("[7] cyan-jade theme captured")
    cyan_primary = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--theme-primary')")
    print(f"[8] cyan-jade --theme-primary = {cyan_primary.strip()!r}")

    # 切到 moonlit-bamboo
    page.evaluate("""
        localStorage.setItem('novel-ai.theme.v1', JSON.stringify({
            currentId: 'moonlit-bamboo',
            custom: []
        }));
    """)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/theme-4-moonlit.png", full_page=False)
    print("[9] moonlit-bamboo theme captured")

    # 切到 dreamy-ink
    page.evaluate("""
        localStorage.setItem('novel-ai.theme.v1', JSON.stringify({
            currentId: 'dreamy-ink',
            custom: []
        }));
    """)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/theme-5-dreamy.png", full_page=False)
    print("[10] dreamy-ink theme captured")

    # 切到 shanshui（墨白）
    page.evaluate("""
        localStorage.setItem('novel-ai.theme.v1', JSON.stringify({
            currentId: 'shanshui',
            custom: []
        }));
    """)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/theme-6-shanshui.png", full_page=False)
    print("[11] shanshui theme captured")
    shan_primary = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--theme-primary')")
    print(f"[12] shanshui --theme-primary = {shan_primary.strip()!r}")

    # 模拟自定义主题（用 data URL）
    custom_data_url = (
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII="
    )
    page.evaluate(f"""
        localStorage.setItem('novel-ai.theme.custom.v1', JSON.stringify([{{
            id: 'custom-test-001',
            name: '测试自定义',
            imageUrl: '{custom_data_url}',
            mode: 'custom',
            palette: {{
                colors: ['#0ea5e9', '#38bdf8', '#0c4a6e', '#bae6fd', '#e0f2fe', '#f0f9ff'],
                primary: '#0ea5e9',
                secondary: '#38bdf8',
                background: '#f0f9ff',
                foreground: '#ffffff',
                primarySoft: 'rgba(14, 165, 233, 0.12)',
                shadow: 'rgba(12, 74, 110, 0.18)'
            }},
            createdAt: Date.now()
        }}]));
        localStorage.setItem('novel-ai.theme.v1', JSON.stringify({{
            currentId: 'custom-test-001',
            custom: []
        }}));
    """)
    page.reload()
    page.wait_for_load_state("networkidle")
    page.screenshot(path="/tmp/theme-7-custom.png", full_page=False)
    print("[13] custom theme captured")
    custom_primary = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--theme-primary')")
    print(f"[14] custom --theme-primary = {custom_primary.strip()!r}")

    # 切回默认 + 清理
    page.evaluate("localStorage.clear()")

    browser.close()
    print("\n=== 验证完成 ===")
