"""
agents.py  – LangGraph multi-agent graph for FitBot
"""
from __future__ import annotations

import json
import os
import re
from typing import Annotated, TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

import database as db

# ── LLM ───────────────────────────────────────────────────────────────────
def _llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        max_tokens=2000,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  1.  PLAN-GENERATION GRAPH
#      Input : user profile dict
#      Output: { nutrition_plan, exercise_plan }
# ═══════════════════════════════════════════════════════════════════════════

class PlanState(TypedDict):
    user: dict
    tdee: float
    nutrition_plan: dict
    exercise_plan: dict


def calculate_tdee(state: PlanState) -> PlanState:
    """Agent: calculate TDEE using Mifflin-St Jeor + activity multiplier."""
    u = state["user"]
    w, h, a = u["weight_kg"], u["height_cm"], u["age"]
    sex = u.get("sex", "male")
    if sex == "female":
        bmr = 10 * w + 6.25 * h - 5 * a - 161
    else:
        bmr = 10 * w + 6.25 * h - 5 * a + 5
    activity_multipliers = {
        "sedentary": 1.2,
        "light":     1.375,
        "moderate":  1.55,
        "active":    1.725,
    }
    activity = u.get("activity_level", "moderate")
    tdee = bmr * activity_multipliers.get(activity, 1.55)
    goal = u["goal"]
    if goal == "fat_loss":
        tdee -= 500
    elif goal == "muscle_gain":
        tdee += 300
    return {**state, "tdee": round(tdee)}


def _calculate_macros(weight_kg: float, tdee: float, goal: str) -> dict:
    """
    Pre-calculate macro targets so the LLM only writes meals.
    All ranges use their MIDPOINT. Carbs = remaining calories (floor 50g).

    MAINTAIN  — Priority: Carbs > Protein > Fat
      Protein: 1.8 g/kg  (midpoint of 1.6–2.0)
      Fat:     0.9 g/kg  (midpoint of 0.8–1.0)
      Carbs:   remainder → highest (moderate protein+fat leave most room)

    FAT LOSS  — Priority: Protein > Fat > Carbs
      Protein: 2.0 g/kg  (midpoint of 1.8–2.2, highest — protects muscle)
      Fat:     0.8 g/kg  (fixed minimum healthy level — kept low)
      Carbs:   remainder → lowest (high protein + lower TDEE squeeze carbs down)

    MUSCLE GAIN  — Priority: Carbs > Protein ≈ Fat
      Protein: 1.8 g/kg  (midpoint of 1.6–2.0)
      Fat:     0.9 g/kg  (midpoint of 0.8–1.0)
      Carbs:   remainder → highest (higher TDEE surplus flows into carbs)
    """
    if goal == "fat_loss":
        protein_g = round(weight_kg * 2.0)  # highest protein to protect muscle
        fat_g     = round(weight_kg * 0.8)  # fixed at minimum healthy level
    elif goal == "muscle_gain":
        protein_g = round(weight_kg * 1.8)  # midpoint of 1.6–2.0
        fat_g     = round(weight_kg * 0.9)  # midpoint of 0.8–1.0
    else:  # maintain
        protein_g = round(weight_kg * 1.8)  # midpoint of 1.6–2.0
        fat_g     = round(weight_kg * 0.9)  # midpoint of 0.8–1.0

    carbs_g = max(round((tdee - protein_g * 4 - fat_g * 9) / 4), 50)
    return {"protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}


def generate_nutrition_plan(state: PlanState) -> PlanState:
    """Agent: create a weekly nutrition plan with pre-calculated, science-based macros."""
    u = state["user"]
    tdee = state["tdee"]
    macros = _calculate_macros(u["weight_kg"], tdee, u["goal"])

    prompt = f"""You are a professional nutritionist. Create a 7-day meal plan.
User profile:
- Name: {u['name']}, Age: {u['age']}, Weight: {u['weight_kg']}kg, Height: {u['height_cm']}cm
- Goal: {u['goal']}
- Daily calorie target: {tdee} kcal

MACRO TARGETS (pre-calculated from body weight — use EXACTLY, do not change):
- Protein: {macros['protein_g']}g ({macros['protein_g'] * 4} kcal)
- Carbs:   {macros['carbs_g']}g ({macros['carbs_g'] * 4} kcal)
- Fat:     {macros['fat_g']}g ({macros['fat_g'] * 9} kcal)

Your job is ONLY to write meal descriptions that fit these macro targets.

Return ONLY valid JSON (no markdown, no explanation) with this structure:
{{
  "daily_calories": {tdee},
  "macros": {{"protein_g": {macros['protein_g']}, "carbs_g": {macros['carbs_g']}, "fat_g": {macros['fat_g']}}},
  "week": {{
    "Monday":    {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}},
    "Tuesday":   {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}},
    "Wednesday": {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}},
    "Thursday":  {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}},
    "Friday":    {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}},
    "Saturday":  {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}},
    "Sunday":    {{"breakfast": "...", "lunch": "...", "dinner": "...", "snacks": "..."}}
  }}
}}"""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = resp.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    plan = json.loads(raw)
    return {**state, "nutrition_plan": plan}


def generate_exercise_plan(state: PlanState) -> PlanState:
    """Agent: ask Gemini to create a weekly exercise plan."""
    u = state["user"]
    prompt = f"""You are a certified personal trainer. Create a 7-day workout plan.
User profile:
- Goal: {u['goal']}, Weight: {u['weight_kg']}kg
- Fitness level: beginner-intermediate

Return ONLY valid JSON (no markdown) with this structure:
{{
  "week": {{
    "Monday":    {{"type": "...", "exercises": [{{"name":"...", "sets": <n>, "reps": "...", "rest_sec": <n>}}]}},
    "Tuesday":   {{"type": "Rest / Active Recovery", "exercises": []}},
    "Wednesday": {{"type": "...", "exercises": [...]}},
    "Thursday":  {{"type": "...", "exercises": [...]}},
    "Friday":    {{"type": "...", "exercises": [...]}},
    "Saturday":  {{"type": "...", "exercises": [...]}},
    "Sunday":    {{"type": "Rest", "exercises": []}}
  }}
}}"""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = resp.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    plan = json.loads(raw)
    return {**state, "exercise_plan": plan}


def build_plan_graph():
    g = StateGraph(PlanState)
    g.add_node("tdee", calculate_tdee)
    g.add_node("nutrition", generate_nutrition_plan)
    g.add_node("exercise", generate_exercise_plan)
    g.add_edge(START, "tdee")
    g.add_edge("tdee", "nutrition")
    g.add_edge("nutrition", "exercise")
    g.add_edge("exercise", END)
    return g.compile()


PLAN_GRAPH = build_plan_graph()


def generate_plans_for_user(user_profile: dict) -> tuple[dict, dict, float]:
    """Run the plan graph and return (nutrition_plan, exercise_plan, tdee)."""
    result = PLAN_GRAPH.invoke({"user": user_profile})
    return result["nutrition_plan"], result["exercise_plan"], result["tdee"]


# ═══════════════════════════════════════════════════════════════════════════
#  2.  CHAT GRAPH
#      Nodes: router → calorie_tracker | fitness_advisor → respond
# ═══════════════════════════════════════════════════════════════════════════

class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    user: dict
    intent: str          # 'food_log' | 'fitness_qa' | 'general'
    food_info: dict      # extracted food + calories
    context: str         # extra context injected into final reply


def router_node(state: ChatState) -> ChatState:
    """Classify the user's last message."""
    last = state["messages"][-1].content
    prompt = f"""Classify this fitness chatbot message into one of:
- food_log    (user mentions eating something specific)
- delete_log  (user wants to delete or remove their last food entry)
- correct_log (user wants to correct or update their last food entry, e.g. "actually I only had half", "correct my last entry")
- youtube     (user asks to see a video, how to do an exercise, show me a tutorial, watch a workout)
- recipe      (user asks for a food recipe, how to cook something, how to make a meal)
- fitness_qa  (question about exercise, workouts, health, body, nutrition)
- general     (greetings, plan questions, calorie questions, progress)
- off_topic   (anything NOT related to fitness, nutrition, health, or sport — e.g. weather, politics, news, technology)

Message: "{last}"
Reply with ONLY one word: food_log OR delete_log OR correct_log OR youtube OR recipe OR fitness_qa OR general OR off_topic"""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    intent = resp.content.strip().lower()
    if intent not in ("food_log", "delete_log", "correct_log", "youtube", "recipe", "fitness_qa", "general", "off_topic"):
        intent = "general"
    return {**state, "intent": intent}


def _search_usda(food_name: str, quantity_str: str) -> dict | None:
    """Look up calories + macros from USDA FoodData API. Returns dict or None."""
    import urllib.request
    import urllib.parse

    api_key = os.environ.get("USDA_API_KEY", "")
    if not api_key:
        return None

    try:
        food_lower = food_name.lower()

        search_query = food_name.strip()
        if not any(w in food_lower for w in ("dried", "cooked", "fried", "boiled", "grilled", "baked", "canned", "frozen")):
            search_query = food_name + " raw"

        params = urllib.parse.urlencode({
            "query": search_query,
            "dataType": "SR Legacy,Foundation",
            "pageSize": 5,
            "api_key": api_key,
        })
        url = f"https://api.nal.usda.gov/fdc/v1/foods/search?{params}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())

        foods = data.get("foods", [])
        if not foods:
            return None

        def score(f):
            desc = f.get("description", "").lower()
            s = 0
            if "raw" in desc or "fresh" in desc: s += 10
            if "dried" in desc or "powder" in desc or "dehydrated" in desc: s -= 10
            if "whole" in desc: s += 3
            if food_lower in desc: s += 5
            return s

        foods.sort(key=score, reverse=True)
        food = foods[0]
        nutrients = food.get("foodNutrients", [])

        # Pull all four macronutrients per 100g
        kcal_per_100g = protein_per_100g = carbs_per_100g = fat_per_100g = None
        for n in nutrients:
            name = n.get("nutrientName", "").lower()
            unit = n.get("unitName", "").upper()
            val  = n.get("value")
            if name in ("energy", "energy (atwater general factors)") and unit == "KCAL":
                kcal_per_100g = val
            elif name in ("protein",) and unit == "G":
                protein_per_100g = val
            elif name in ("carbohydrate, by difference",) and unit == "G":
                carbs_per_100g = val
            elif name in ("total lipid (fat)",) and unit == "G":
                fat_per_100g = val

        if kcal_per_100g is None:
            return None

        # Parse quantity → grams (same logic as before)
        qty = quantity_str.lower().strip()
        food_lower = food_name.lower()
        grams = None
        num_match = re.search(r"(\d+\.?\d*)", qty)
        num = float(num_match.group(1)) if num_match else 1.0

        if "kg" in qty:             grams = num * 1000
        elif "g" in qty or "gram" in qty: grams = num
        elif "oz" in qty:           grams = num * 28.35
        elif "lb" in qty or "pound" in qty: grams = num * 453.6
        elif "cup" in qty:          grams = num * 240
        elif "tbsp" in qty or "tablespoon" in qty: grams = num * 15
        elif "tsp" in qty or "teaspoon" in qty: grams = num * 5
        elif "half" in qty or "1/2" in qty:
            if "chicken breast" in food_lower: grams = 87
            elif "egg" in food_lower:          grams = 25
            elif "banana" in food_lower:       grams = 60
            elif "apple" in food_lower:        grams = 90
            else:                              grams = 50
        elif "slice" in qty:
            if "bread" in food_lower:          grams = 30
            elif "cheese" in food_lower:       grams = 20
            elif "pizza" in food_lower:        grams = 100
            elif "turkey" in food_lower or "ham" in food_lower: grams = 28
            else:                              grams = 30
        elif "piece" in qty or "serving" in qty:
            grams = num * 100
        else:
            TYPICAL_WEIGHTS = {
                "egg white": 33, "egg yolk": 17, "egg": 50, "large egg": 56,
                "small egg": 38, "medium egg": 44, "banana": 118, "apple": 182,
                "orange": 131, "chicken breast": 174, "chicken thigh": 109,
                "chicken leg": 114, "salmon fillet": 170, "tuna can": 142,
                "avocado": 150, "potato": 150, "sweet potato": 130, "carrot": 61,
                "tomato": 123, "onion": 110, "garlic clove": 3, "date": 24,
                "walnut": 5, "almond": 1, "strawberry": 12,
            }
            matched = next((w for k, w in TYPICAL_WEIGHTS.items() if k in food_lower), None)
            grams = num * matched if matched else num * 100

        factor = grams / 100
        return {
            "calories":  round(kcal_per_100g * factor),
            "protein_g": round((protein_per_100g or 0) * factor, 1),
            "carbs_g":   round((carbs_per_100g  or 0) * factor, 1),
            "fat_g":     round((fat_per_100g    or 0) * factor, 1),
        }

    except Exception:
        return None


def calorie_tracker_node(state: ChatState) -> ChatState:
    """Extract food items and estimate calories; log to DB."""
    print("USDA KEY:", os.environ.get("USDA_API_KEY", "NOT SET"))  # ← add this line
    last = state["messages"][-1].content
    user = state["user"]

    prompt = f"""You are a nutrition expert and calorie database.
The user said: "{last}"

Extract all food items mentioned and estimate calories AND macros accurately.
Return ONLY valid JSON:
{{
  "items": [
    {{"name": "...", "quantity": "...", "calories": <number>, "protein_g": <number>, "carbs_g": <number>, "fat_g": <number>}},
    ...
  ],
  "total_calories": <number>,
  "total_protein_g": <number>,
  "total_carbs_g": <number>,
  "total_fat_g": <number>,
  "meal_type": "breakfast" | "lunch" | "dinner" | "snack"
}}"""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = resp.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        food_info = json.loads(raw)
    except Exception:
        consumed = db.get_today_calories(user["id"])
        remaining = user["tdee"] - consumed
        context = (
            f"Total consumed today: {consumed:.0f} kcal.\n"
            f"Remaining budget: {remaining:.0f} kcal (daily target {user['tdee']} kcal)."
        )
        return {**state, "food_info": {}, "context": context}

    # Try to get accurate calories+macros from USDA for each item
    usda_used = False
    for item in food_info["items"]:
        usda_data = _search_usda(item["name"], item["quantity"])
        if usda_data is not None:
            item["calories"]  = usda_data["calories"]
            item["protein_g"] = usda_data["protein_g"]
            item["carbs_g"]   = usda_data["carbs_g"]
            item["fat_g"]     = usda_data["fat_g"]
            item["source"]    = "USDA"
            usda_used = True
        else:
            item.setdefault("protein_g", 0)
            item.setdefault("carbs_g",   0)
            item.setdefault("fat_g",     0)
            item["source"] = "estimated"

    # Recalculate totals from (possibly updated) items
    food_info["total_calories"]  = sum(i["calories"]  for i in food_info["items"])
    food_info["total_protein_g"] = round(sum(i.get("protein_g", 0) for i in food_info["items"]), 1)
    food_info["total_carbs_g"]   = round(sum(i.get("carbs_g",   0) for i in food_info["items"]), 1)
    food_info["total_fat_g"]     = round(sum(i.get("fat_g",     0) for i in food_info["items"]), 1)

    # Log to database (with macros)
    description = ", ".join(f"{i['quantity']} {i['name']}" for i in food_info["items"])
    db.log_food(
        user["id"],
        food_info["meal_type"],
        description,
        food_info["total_calories"],
        protein_g=food_info["total_protein_g"],
        carbs_g=food_info["total_carbs_g"],
        fat_g=food_info["total_fat_g"],
    )

    # Build context for the responder — calories + macros
    consumed  = db.get_today_calories(user["id"])
    macros    = db.get_today_macros(user["id"])
    plan      = db.get_latest_plan(user["id"])
    remaining = user["tdee"] - consumed

    source_note = "✅ Calories from USDA database." if usda_used else "⚠️ Calories estimated by AI."

    # Macro targets from the nutrition plan (if available)
    if plan and "macros" in plan.get("nutrition_plan", {}):
        targets = plan["nutrition_plan"]["macros"]
        protein_target = targets.get("protein_g", 0)
        carbs_target   = targets.get("carbs_g",   0)
        fat_target     = targets.get("fat_g",     0)
        macro_target_line = (
            f"Daily macro targets — "
            f"Protein: {protein_target}g | Carbs: {carbs_target}g | Fat: {fat_target}g\n"
        )
        macro_remaining_line = (
            f"Macros remaining — "
            f"Protein: {max(0, round(protein_target - macros['protein_g']))}g | "
            f"Carbs: {max(0, round(carbs_target - macros['carbs_g']))}g | "
            f"Fat: {max(0, round(fat_target - macros['fat_g']))}g\n"
        )
    else:
        macro_target_line    = ""
        macro_remaining_line = ""

    context = (
        f"Food logged: {description} ({food_info['total_calories']} kcal). {source_note}\n"
        f"  → Protein: {food_info['total_protein_g']}g | "
        f"Carbs: {food_info['total_carbs_g']}g | Fat: {food_info['total_fat_g']}g\n"
        f"Total consumed today: {consumed:.0f} kcal | "
        f"Protein: {macros['protein_g']:.0f}g | "
        f"Carbs: {macros['carbs_g']:.0f}g | "
        f"Fat: {macros['fat_g']:.0f}g\n"
        f"Remaining calorie budget: {remaining:.0f} kcal (daily target {user['tdee']} kcal).\n"
        f"{macro_target_line}"
        f"{macro_remaining_line}"
    )
    return {**state, "food_info": food_info, "context": context}


def delete_log_node(state: ChatState) -> ChatState:
    """
    Smart delete: if the user mentions a specific item within a meal
    (e.g. 'remove the donut from breakfast'), update that meal entry
    in place rather than deleting the whole row.
    Falls back to deleting the last entry if no specific item is found.
    """
    user = state["user"]
    last = state["messages"][-1].content

    # Ask LLM to identify: which item to remove, and which meal it belongs to
    prompt = f"""The user wants to remove a specific food item from their log.
Message: "{last}"

Identify:
1. The specific item they want to remove (e.g. "donut", "eclaire", "coffee")
2. The meal it belongs to: breakfast | lunch | dinner | snack
   If no meal is mentioned, reply "unknown".

Reply ONLY with valid JSON:
{{"item_to_remove": "...", "meal": "breakfast" | "lunch" | "dinner" | "snack" | "unknown"}}"""

    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = resp.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        parsed = json.loads(raw)
        item_to_remove = parsed.get("item_to_remove", "").strip()
        meal = parsed.get("meal", "unknown").strip().lower()
    except Exception:
        item_to_remove, meal = "", "unknown"

    # If we know the meal and item, try a surgical update
    if item_to_remove and meal != "unknown":
        existing = db.get_meal_log(user["id"], meal)
        if existing:
            # Ask LLM to rewrite the description without the removed item
            rewrite_prompt = f"""A food log entry needs to be updated by removing one item.

Current log entry: "{existing['description']}"
Current calories: {existing['calories']} kcal
Item to remove: "{item_to_remove}"

Return ONLY valid JSON with the updated entry (excluding the removed item):
{{"updated_description": "...", "updated_calories": <number>}}"""

            resp2 = llm.invoke([HumanMessage(content=rewrite_prompt)])
            raw2 = resp2.content.strip()
            raw2 = re.sub(r"^```[a-z]*\n?", "", raw2)
            raw2 = re.sub(r"\n?```$", "", raw2)

            try:
                updated = json.loads(raw2)
                new_desc = updated["updated_description"].strip()
                new_cals = float(updated["updated_calories"])

                db.update_food_log(existing["id"], new_desc, new_cals)

                consumed = db.get_today_calories(user["id"])
                macros   = db.get_today_macros(user["id"])
                remaining = user["tdee"] - consumed
                context = (
                    f"Removed '{item_to_remove}' from {meal}. "
                    f"Updated {meal} log: '{new_desc}' ({new_cals:.0f} kcal).\n"
                    f"Total consumed today: {consumed:.0f} kcal | "
                    f"Protein: {macros['protein_g']:.0f}g | "
                    f"Carbs: {macros['carbs_g']:.0f}g | "
                    f"Fat: {macros['fat_g']:.0f}g\n"
                    f"Remaining calorie budget: {remaining:.0f} kcal (daily target {user['tdee']} kcal)."
                )
                return {**state, "food_info": {}, "context": context}
            except Exception:
                pass  # fall through to full delete

    deleted = db.delete_last_food_log(user["id"])
    consumed  = db.get_today_calories(user["id"])
    macros    = db.get_today_macros(user["id"])
    remaining = user["tdee"] - consumed
    if deleted:
        context = (
            f"Last food entry deleted: {deleted['description']} ({deleted['calories']} kcal).\n"
            f"Total consumed today: {consumed:.0f} kcal | "
            f"Protein: {macros['protein_g']:.0f}g | "
            f"Carbs: {macros['carbs_g']:.0f}g | "
            f"Fat: {macros['fat_g']:.0f}g\n"
            f"Remaining calorie budget: {remaining:.0f} kcal (daily target {user['tdee']} kcal)."
        )
    else:
        context = "No food entries found to delete for today."
    return {**state, "food_info": {}, "context": context}


def correct_log_node(state: ChatState) -> ChatState:
    """Delete last entry and log the corrected one."""
    user = state["user"]
    last = state["messages"][-1].content

    # Delete the last entry
    deleted = db.delete_last_food_log(user["id"])

    # Now extract the corrected food from the message
    prompt = f"""You are a nutrition expert and calorie database.
The user is correcting their last food entry. They said: "{last}"

Extract the CORRECTED food items and estimate calories accurately.
Return ONLY valid JSON:
{{
  "items": [
    {{"name": "...", "quantity": "...", "calories": <number>}},
    ...
  ],
  "total_calories": <number>,
  "meal_type": "breakfast" | "lunch" | "dinner" | "snack"
}}"""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    raw = resp.content.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        food_info = json.loads(raw)
        description = ", ".join(
            f"{i['quantity']} {i['name']}" for i in food_info["items"]
        )
        db.log_food(
            user["id"],
            food_info["meal_type"],
            description,
            food_info["total_calories"],
        )
        consumed  = db.get_today_calories(user["id"])
        macros    = db.get_today_macros(user["id"])
        remaining = user["tdee"] - consumed
        old_desc = deleted["description"] if deleted else "previous entry"
        context = (
            f"Corrected: removed '{old_desc}', logged '{description}' ({food_info['total_calories']} kcal) instead.\n"
            f"Total consumed today: {consumed:.0f} kcal | "
            f"Protein: {macros['protein_g']:.0f}g | "
            f"Carbs: {macros['carbs_g']:.0f}g | "
            f"Fat: {macros['fat_g']:.0f}g\n"
            f"Remaining calorie budget: {remaining:.0f} kcal (daily target {user['tdee']} kcal)."
        )
        return {**state, "food_info": food_info, "context": context}
    except Exception:
        consumed = db.get_today_calories(user["id"])
        remaining = user["tdee"] - consumed
        context = (
            f"Last entry deleted. Could not parse corrected food.\n"
            f"Total consumed today: {consumed:.0f} kcal.\n"
            f"Remaining budget: {remaining:.0f} kcal."
        )
        return {**state, "food_info": {}, "context": context}


def youtube_node(state: ChatState) -> ChatState:
    """Search YouTube for an exercise video and return the top result."""
    import urllib.request
    import urllib.parse
    from langchain_core.messages import AIMessage

    last = state["messages"][-1].content

    # Ask LLM to extract the exercise name
    prompt = f"""Extract the exercise or workout name from this message: "{last}"
Reply with ONLY the exercise name, e.g. "squat", "push up", "deadlift tutorial". Nothing else."""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    query = resp.content.strip() + " exercise tutorial"

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return {**state, "messages": [AIMessage(content="YOUTUBE_API_KEY not set. Cannot search YouTube.")]}

    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 3,
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        items = data.get("items", [])
        if not items:
            reply = AIMessage(content=f"No YouTube videos found for '{query}'.")
        else:
            videos = []
            for item in items:
                vid_id = item["id"]["videoId"]
                title  = item["snippet"]["title"]
                videos.append({"title": title, "video_id": vid_id,
                                "url": f"https://www.youtube.com/watch?v={vid_id}"})
            # Put YOUTUBE_RESULTS directly in messages so responder is skipped
            reply = AIMessage(content="YOUTUBE_RESULTS:" + json.dumps(videos))
    except Exception as e:
        reply = AIMessage(content=f"YouTube search failed: {e}")

    return {**state, "messages": [reply]}


def recipe_node(state: ChatState) -> ChatState:
    """Search YouTube for a healthy recipe video."""
    import urllib.request
    import urllib.parse
    from langchain_core.messages import AIMessage

    last = state["messages"][-1].content

    # Ask LLM to extract the food/recipe name
    prompt = f"""Extract the food or recipe name from this message: "{last}"
Reply with ONLY the food or recipe name, e.g. "grilled chicken", "oatmeal", "protein pancakes". Nothing else."""
    llm = _llm()
    resp = llm.invoke([HumanMessage(content=prompt)])
    query = resp.content.strip() + " healthy recipe"

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return {**state, "messages": [AIMessage(content="YOUTUBE_API_KEY not set. Cannot search YouTube.")]}

    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 3,
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        items = data.get("items", [])
        if not items:
            reply = AIMessage(content=f"No recipe videos found for '{query}'.")
        else:
            videos = []
            for item in items:
                vid_id = item["id"]["videoId"]
                title  = item["snippet"]["title"]
                videos.append({"title": title, "video_id": vid_id,
                                "url": f"https://www.youtube.com/watch?v={vid_id}"})
            reply = AIMessage(content="YOUTUBE_RESULTS:" + json.dumps(videos))
    except Exception as e:
        reply = AIMessage(content=f"YouTube search failed: {e}")

    return {**state, "messages": [reply]}


def fitness_qa_node(state: ChatState) -> ChatState:
    """Add relevant plan context for fitness questions."""
    user = state["user"]
    plan = db.get_latest_plan(user["id"])
    if plan:
        snippet = json.dumps(plan["exercise_plan"]["week"], indent=2)[:800]
        context = f"User's exercise plan (excerpt):\n{snippet}"
    else:
        context = "No exercise plan on file yet."
    return {**state, "context": context}


def responder_node(state: ChatState) -> ChatState:
    """Final node: craft the assistant reply using history + context."""
    user = state["user"]
    plan = db.get_latest_plan(user["id"])

    system = f"""You are FitBot, an AI fitness coach. You ONLY answer questions related to:
- Fitness, exercise, and workouts
- Nutrition, food, and calories
- Health, body composition, and wellness
- The user's personal plans and progress

If the user asks about ANYTHING else (weather, politics, technology, general knowledge, etc.),
politely refuse and redirect them. Say something like:
"I'm only able to help with fitness, nutrition, and health topics. Got any questions about your workout or diet?"

User profile:
- Name: {user['name']}, Age: {user['age']}
- Weight: {user['weight_kg']} kg, Height: {user['height_cm']} cm
- Goal: {user['goal']}
- Daily calorie target: {user['tdee']} kcal

{state.get('context', '')}

Rules:
1. Be encouraging, specific, and evidence-based.
2. If food was logged, clearly state kcal eaten, kcal remaining, and the macros (protein/carbs/fat) eaten and remaining vs. daily targets. Give brief advice.
3. Keep answers concise (2-4 short paragraphs max).
4. Use emojis sparingly.
"""
    history = db.get_chat_history(user["id"], limit=16, today_only=True)
    msgs = [SystemMessage(content=system)]
    for h in history[:-1]:
        if h["role"] == "user":
            msgs.append(HumanMessage(content=h["content"]))
        else:
            from langchain_core.messages import AIMessage
            msgs.append(AIMessage(content=h["content"]))
    msgs.append(state["messages"][-1])

    llm = _llm()
    resp = llm.invoke(msgs)
    return {**state, "messages": [resp]}


def off_topic_node(state: ChatState) -> ChatState:
    """Immediately reject off-topic questions."""
    from langchain_core.messages import AIMessage
    reply = AIMessage(content=(
        "I'm FitBot — I can only help with fitness, nutrition, and health topics. 💪\n"
        "Got any questions about your workout, diet, or progress?"
    ))
    return {**state, "messages": [reply]}


def _route(state: ChatState) -> str:
    intent = state.get("intent", "general")
    if intent == "food_log":
        return "calorie_tracker"
    if intent == "delete_log":
        return "delete_log"
    if intent == "correct_log":
        return "correct_log"
    if intent == "youtube":
        return "youtube"
    if intent == "recipe":
        return "recipe"
    if intent == "off_topic":
        return "off_topic"
    if intent == "fitness_qa":
        return "fitness_qa"
    return "responder"


def build_chat_graph():
    g = StateGraph(ChatState)
    g.add_node("router", router_node)
    g.add_node("calorie_tracker", calorie_tracker_node)
    g.add_node("delete_log", delete_log_node)
    g.add_node("correct_log", correct_log_node)
    g.add_node("youtube", youtube_node)
    g.add_node("recipe", recipe_node)
    g.add_node("off_topic", off_topic_node)
    g.add_node("fitness_qa", fitness_qa_node)
    g.add_node("responder", responder_node)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", _route, {
        "calorie_tracker": "calorie_tracker",
        "delete_log": "delete_log",
        "correct_log": "correct_log",
        "youtube": "youtube",
        "recipe": "recipe",
        "off_topic": "off_topic",
        "fitness_qa": "fitness_qa",
        "responder": "responder",
    })
    g.add_edge("calorie_tracker", "responder")
    g.add_edge("delete_log", "responder")
    g.add_edge("correct_log", "responder")
    g.add_edge("youtube", END)
    g.add_edge("recipe", END)
    g.add_edge("off_topic", END)
    g.add_edge("fitness_qa", "responder")
    g.add_edge("responder", END)
    return g.compile()


CHAT_GRAPH = build_chat_graph()


def chat(user: dict, user_message: str) -> str:
    """Run one turn of the chat graph and return assistant reply."""
    db.save_message(user["id"], "user", user_message)
    result = CHAT_GRAPH.invoke({
        "messages": [HumanMessage(content=user_message)],
        "user": user,
        "intent": "",
        "food_info": {},
        "context": "",
    })
    reply = result["messages"][-1].content
    db.save_message(user["id"], "assistant", reply)
    return reply