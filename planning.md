# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:** 
This tool searches through listings in data/listings.json. It first matches on size and caps price of the listings at max_price, and then semantically matches on description. It returns the top 3 listings, sorted by relevance.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Description of item to be searched for, qualitatively
- `size` (str): The size of the item, must match exactly
- `max_price` (float): The maximum price of the item - the returned item must have price <= max price

**What it returns:**
The tool returns a list of the top 3 listings with all attributes, sorted in order of decreasing relevance.

**What happens if it fails or returns nothing:**
If the tool fails or returns nothing, the agent should stop and help the user debug.

---

### Tool 2: suggest_outfit

**What it does:**
 Given a specific item and the user's current wardrobe, suggests one or more complete outfit combinations.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A dict containing id, name, category, style_tags, colors of the new item to be considered.
- `wardrobe` (dict): A dict containing a key 'item', which references a list of various clothes, defined as in the schema of listings.json.

**What it returns:**
It returns one or more complete outfit combinations.

**What happens if it fails or returns nothing:**
If the wardrobe is empty/minimal or nothing can be suggested, it reports that to the user and stops.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable description of a complete outfit — the kind of thing someone would caption an Instagram post with. Must produce something different each time for different inputs.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (dict): A dict containing a key 'item', which references a list of various clothes, defined as in the schema of listings.json.
- `new_item` (dict): A dict containing id, name, category, style_tags, colors of the new item to be considered.

**What it returns:**
A short description of the complete outfit, like a caption for an instagram post.

**What happens if it fails or returns nothing:**
Return nothing.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
After search_listings runs, check if the results are empty. If yest, set an error messsage and return early. If not, set selected_item to either
the item in the query or the first item and proceed to suggest_outfit.

After suggest_outfit runs, check if an error occured. If yes, set an error message and return early. If not, proceed to create_fit_card with the 
suggested outfit and the selected_item from above.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
The agent stores the query, what's been parsed, search results, the selected item, wardrobe, outfit suggestions, fit card, and an error field. It is passed as a dict between tool calls.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = \                       |
    combine_first(user_query, results[0])                 │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session
---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I'll use Claude and give it my specs above for the tools. I will give it access to the data/ folder so it can see the schema. I will then test each tool as a unit test.

**Milestone 4 — Planning loop and state management:**
I'll use Claude and give it the planning loop and the architecture diagram above.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
*Search* call tool search_listings("vintage graphic tee", size="M", max_price=30.0), which returns 3 matching listings sorted by relevance. FitFindr picks the top result: "Faded Band Tee — $22, Depop, Good condition." If this returns nothing, FitFindr tells the user to try something else and stops.

**Step 2:**
*Suggest Outfit* call tool suggest_outfit(new_item=<band tee>, wardrobe=<user's wardrobe>), which returns: "Pair this with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape."

**Step 3:**
*Create Fit Card* call tool create_fit_card(outfit=<suggestion>, new_item=<band tee>), which returns: "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"

**Final output to user:**
"thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"
