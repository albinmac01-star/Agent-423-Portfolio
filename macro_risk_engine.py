from supabase import create_client, Client

def get_gold_macro_bias() -> dict:
    """
    Connects to the Supabase AI Vault and returns a mathematical 
    macro bias for XAUUSD to be used by trading algorithms.
    """


       try:
        supabase: Client = create_client(url, key)
        response = supabase.table("macro_state").select("*").eq("id", 1).execute()


        
        macro_data = response.data[0]

        url = settings.SUPABASE_URL
        key = settings.SUPABASE_KEY
        
        geo_status = macro_data['geopolitics']['status']
        fed_stance = macro_data['central_bank']['fed_stance']
        trade_status = macro_data['trade_and_tariffs']['status']
        
        bullish_score = 0
        bearish_score = 0

        # Logic Gates
        if geo_status == "ELEVATED": bullish_score += 1
        elif geo_status == "DE-ESCALATING": bearish_score += 1
            
        if fed_stance == "HAWKISH": bearish_score += 1
        elif fed_stance == "DOVISH": bullish_score += 1

        if trade_status == "ACTIVE_THREAT": bullish_score += 1

        # Determine final permission
        if bullish_score > bearish_score:
            bias = "LONG_ONLY"
        elif bearish_score > bullish_score:
            bias = "SHORT_ONLY"
        else:
            bias = "NEUTRAL"

        # Return the hard data as a dictionary so a bot can easily read it
        return {
            "status": "SUCCESS",
            "recommended_bias": bias,
            "bullish_score": bullish_score,
            "bearish_score": bearish_score
        }

    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

# --- TESTING THE MODULE ---
# This bottom section only runs if you execute this specific file directly.
if __name__ == "__main__":
    print("Testing Macro Risk Engine...")
    result = get_gold_macro_bias()
    print(result)
