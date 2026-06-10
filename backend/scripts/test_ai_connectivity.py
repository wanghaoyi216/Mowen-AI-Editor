"""
AI 接口连通性测试脚本
用于验证 NVIDIA NIM API 和 Tavily API 配置是否正确
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.integrations.openrouter_client import OpenRouterClient
from app.integrations.tavily_client import build_tavily_client
from app.core.config import settings
from app.services.openrouter_service import generate_with_openrouter_fallback


async def test_nvidia_connectivity() -> bool:
    print("\n" + "=" * 60)
    print("NVIDIA NIM API 连通性测试")
    print("=" * 60)

    print(f"\n[配置检查]")
    print(f"  NVIDIA_API_KEY: {'已配置 ✓' if settings.nvidia_api_key else '✗ 未配置'}")
    print(f"  NVIDIA_BASE_URL: {settings.nvidia_base_url}")

    if not settings.nvidia_api_key:
        print("\n✗ 错误: NVIDIA_API_KEY 未配置")
        print("请在 .env 文件中设置有效的 NVIDIA NIM API Key（形如 nvapi-...）")
        return False

    client = OpenRouterClient(
        api_key=settings.nvidia_api_key,
        base_url=settings.nvidia_base_url,
    )
    
    print(f"\n[测试 1: 列出可用模型]")
    try:
        models_response = client.list_models()
        models = models_response.get("data", [])
        print(f"  ✓ 成功获取 {len(models)} 个模型")
        if models:
            print(f"  示例模型: {models[0].get('id', 'N/A')}")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False
    
    print(f"\n[测试 2: 列出免费模型]")
    try:
        free_models = client.list_free_models()
        print(f"  ✓ 成功获取 {len(free_models)} 个免费模型")
        if free_models:
            print(f"  示例: {free_models[0].get('id', 'N/A')}")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
    
    print(f"\n[测试 3: 发送聊天请求]")
    try:
        response_payload = generate_with_openrouter_fallback(
            system_prompt="你是一个测试助手。请回复 'AI 连接成功！'",
            user_prompt="你好，请确认连接正常",
            preferred_keywords=["qwen", "deepseek", "mistral", "llama", "gemma", "kimi"],
            max_model_attempts=12,
        )
        response = response_payload["completion"]
        choices = response.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        print(f"  ✓ AI 回复: {content[:100]}")
        print(f"  使用模型: {response.get('model', 'N/A')}")
        attempts = response_payload.get("attempts", [])
        if attempts:
            print("  模型尝试:")
            for attempt in attempts:
                status = attempt.get("status")
                status_code = attempt.get("status_code")
                suffix = f" HTTP {status_code}" if status_code else ""
                print(f"    - {attempt.get('model_id')}: {status}{suffix}")
        usage = response.get("usage", {})
        print(f"  Token 用量: prompt={usage.get('prompt_tokens', 'N/A')}, completion={usage.get('completion_tokens', 'N/A')}")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False
    
    print(f"\n{'=' * 60}")
    print("✓ OpenRouter API 测试通过！")
    print("=" * 60)
    return True


def test_tavily_connectivity() -> bool:
    print("\n" + "=" * 60)
    print("Tavily API 连通性测试")
    print("=" * 60)
    
    print(f"\n[配置检查]")
    print(f"  TAVILY_KEY: {'已配置 ✓' if settings.tavily_key else '✗ 未配置'}")
    
    if not settings.tavily_key:
        print("\n✗ 错误: TAVILY_KEY 未配置")
        print("请在 .env 文件中设置有效的 Tavily API Key")
        return False
    
    tavily_client = build_tavily_client()
    if tavily_client is None:
        print("\n✗ 错误: 无法创建 Tavily 客户端")
        return False
    
    print(f"\n[测试: 执行搜索]")
    try:
        result = tavily_client.search(
            query="Python programming language",
            max_results=3,
            search_depth="basic",
        )
        results = result.get("results", [])
        print(f"  ✓ 成功获取 {len(results)} 条搜索结果")
        if results:
            first = results[0]
            print(f"  首条标题: {first.get('title', 'N/A')}")
            print(f"  首条URL: {first.get('url', 'N/A')[:60]}...")
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return False
    
    print(f"\n{'=' * 60}")
    print("✓ Tavily API 测试通过！")
    print("=" * 60)
    return True


async def main():
    print("\n" + "#" * 60)
    print("#           AI 服务连通性测试套件                     #")
    print("#" * 60)
    
    nvidia_ok = await test_nvidia_connectivity()
    tavily_ok = test_tavily_connectivity()

    print("\n" + "#" * 60)
    print("#                    测试总结                         #")
    print("#" * 60)
    print(f"\n  NVIDIA NIM API: {'✓ 通过' if nvidia_ok else '✗ 失败'}")
    print(f"  Tavily API:     {'✓ 通过' if tavily_ok else '✗ 失败'}")

    all_ok = nvidia_ok and tavily_ok
    print(f"\n  {'所有测试通过！' if all_ok else '部分测试失败，请检查配置'}")
    print(f"\n{'#' * 60}\n")
    
    return all_ok


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
