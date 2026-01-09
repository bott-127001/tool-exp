import asyncio
from auto_auth import automated_oauth_login

async def test():
    print("🧪 Testing automated OAuth login...\n")
    result = await automated_oauth_login("samarth")
    if result:
        print(f"\n✅ SUCCESS! Token received: {result[:30]}...")
    else:
        print("\n❌ FAILED - Check the browser window and error messages")

if __name__ == "__main__":
    asyncio.run(test())