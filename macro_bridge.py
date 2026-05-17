from supabase import create_client, Client
from config import settings

SUPABASE_KEY = settings.SUPABASE_KEY


# Establish the Bridge
supabase: Client = create_client(url, key)

try:
    # Fetch the raw data
    response = supabase.table("macro_state").select("*").eq("id", 1).execute()
    
    # 2. Extract the Payload
    macro_data = response.data[0]
    
    # 3. Parse the Variables
    geo_status = macro_data['geopolitics']['status']
    fed_stance = macro_data['central_bank']['fed_stance']
    trade_status = macro_data['trade_and_tariffs']['status']
    ai_overall_bias = macro_data.get('overall_gold_bias', 'NEUTRAL')
    
    print("\n[+] AI MACRO STATE ACQUIRED")
    print(f"    Geopolitics: {geo_status}")
    print(f"    Fed Stance:  {fed_stance}")
    print(f"    Tariffs:     {trade_status}")
    print(f"    Agent 6 Bias: {ai_overall_bias}\n")

    # 4. The XAUUSD (Gold) Logic Engine
    print("[*] EVALUATING XAUUSD MACRO CONFLUENCE...")
    
    bullish_score = 0
    bearish_score = 0

    # Logic Gate 1: Safe Haven Demand
    if geo_status == "ELEVATED":
        print("    [+] Geopolitical risk ELEVATED. Safe haven demand favors LONG Gold.")
        bullish_score += 1
    elif geo_status == "DE-ESCALATING":
        print("    [-] Geopolitical risk dropping. Safe haven premium evaporating.")
        bearish_score += 1
        
    # Logic Gate 2: The Yield Threat
    if fed_stance == "HAWKISH":
        print("    [-] Fed is HAWKISH. High bond yields pressure non-yielding Gold.")
        bearish_score += 1
    elif fed_stance == "DOVISH":
        print("    [+] Fed is DOVISH. Lower yields weaken the Dollar, favoring Gold.")
        bullish_score += 1

    # Logic Gate 3: The Inflation Hedge
    if trade_status == "ACTIVE_THREAT":
        print("    [+] Active tariff threats detected. Inflationary pressure favors LONG Gold.")
        bullish_score += 1

    # Final Execution Protocol
    print("\n[$$] XAUUSD TECHNICAL ALIGNMENT PROTOCOL:")
    if bullish_score > bearish_score:
        print("     -> Macro heavily favors LONG setups. (Look for support bounces)")
    elif bearish_score > bullish_score:
        print("     -> Macro heavily favors SHORT setups. (Look for resistance rejections)")
    else:
        print("     -> Macro is CONFLICTED. Trade purely on technical levels with strict stops.")
    print("\n")

except Exception as e:
    print(f"Bridge failed to connect. Error: {e}")
    
