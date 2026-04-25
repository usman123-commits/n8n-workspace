import json, sys

with open('workflows/drafts/cold-email/CE1-fresh.json', 'rb') as f:
    wf = json.loads(f.read().decode('utf-8', errors='replace'))

# ── Updated Combine Data — regex extract contacts from full raw text ──────────
new_combine_code = r"""// Merge all pages + regex-extract contacts BEFORE truncation
const prev = $('Extract Apify Data').item.json;

const getRaw = (nodeName) => {
  try {
    const item = $(nodeName).item.json;
    return (item.data || item.body || '').toString();
  } catch(e) { return ''; }
};

const homepageRaw = getRaw('Jina Website Fetch');
const contactRaw  = getRaw('Jina Contact Fetch');
const aboutRaw    = getRaw('Jina About Fetch');

// ── REGEX EXTRACTION on full untruncated text ───────────────────────────────
const allRaw = [homepageRaw, contactRaw, aboutRaw].join('\n');

// Extract all emails (deduplicated)
const emailMatches = [...new Set(
  (allRaw.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g) || [])
  .filter(e => !e.match(/\.(png|jpg|jpeg|gif|svg|webp|css|js)$/i))  // skip image filenames
)];

// Extract all phone numbers (deduplicated)
const phoneMatches = [...new Set(
  (allRaw.match(/\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}/g) || [])
  .map(p => p.trim())
)];

// ── STRIP NOISE before truncation ───────────────────────────────────────────
const stripNoise = (text) => text
  .replace(/!\[.*?\]\(.*?\)/g, '')           // remove ![Image](url)
  .replace(/\*\s+\[.*?\]\(https?:\/\/[^\)]+\)\n?/g, '')  // remove nav bullet links
  .replace(/\[Skip to.*?\]\(.*?\)\n?/gi, '') // remove skip-to links
  .replace(/\n{3,}/g, '\n\n')
  .trim();

const homepageClean = stripNoise(homepageRaw);
const contactClean  = stripNoise(contactRaw);
const aboutClean    = stripNoise(aboutRaw);

// Homepage: first 2000 + last 600 (footer)
const homepageMain   = homepageClean.substring(0, 2000);
const homepageFooter = homepageClean.length > 2600
  ? '\n=== FOOTER ===\n' + homepageClean.substring(homepageClean.length - 600)
  : '';

// Contact: skip if duplicate of homepage
const contactSection = contactClean && contactClean.substring(0, 200) !== homepageClean.substring(0, 200)
  ? '=== CONTACT PAGE ===\n' + contactClean.substring(0, 1200)
  : '';

// About: first 5000 clean chars
const aboutSection = aboutClean
  ? '=== ABOUT PAGE ===\n' + aboutClean.substring(0, 5000)
  : '';

const websiteText = [
  '=== HOMEPAGE ===',
  homepageMain + homepageFooter,
  contactSection,
  aboutSection
].filter(Boolean).join('\n\n');

return [{ json: {
  ...prev,
  websiteText,
  foundEmails: emailMatches,
  foundPhones: phoneMatches
} }];"""

# ── Update Claude prompt to receive pre-extracted contacts ────────────────────
new_claude_content = (
    "You are an ICP (Ideal Customer Profile) scoring engine AND contact extractor for a cleaning business automation company called Zelvop. "
    "We sell scheduling, dispatch, and operations software to cleaning companies.\\n\\n"
    "Do TWO things:\\n\\n"
    "**TASK 1 — Score this lead from 1-10:**\\n\\n"
    "**High Weight:**\\n"
    "- Team size: Reviews mentioning 'the team', 'crew', multiple cleaners = higher score\\n"
    "- Booking method: WhatsApp/phone-only = good (manual pain). Online booking system = less need for our product\\n"
    "- Airbnb/vacation rental cleaning mentioned in reviews or website = high score (proven use case)\\n"
    "- Franchise/chain brand detected = auto-disqualify (score 1)\\n\\n"
    "**Medium Weight:**\\n"
    "- Review count: 40-80 is sweet spot (established but not enterprise). Under 20 = too small, over 150 = too big\\n"
    "- Owner responds to reviews personally = decision maker accessible\\n\\n"
    "**TASK 2 — Identify the best contact:**\\n"
    "- ownerFirstName: Look in About page text for owner/founder name. Also check review responses for signatures\\n"
    "- ownerLastName: Same sources\\n"
    "- email: Pre-extracted emails are listed below — pick the most likely BUSINESS contact email (prefer info@, hello@, owner name). Ignore noreply@, support@, or image filenames\\n"
    "- phone: Pre-extracted phones listed below — pick the main business number\\n\\n"
    "**Lead Data:**\\n"
    "- Business: \" + $json.businessName + \"\\n"
    "- City: \" + $json.city + \"\\n"
    "- Category: \" + $json.category + \"\\n"
    "- Rating: \" + $json.totalScore + \"\\n"
    "- Review Count: \" + $json.reviewsCount + \"\\n"
    "- Has Online Booking: \" + $json.hasBookingLink + \"\\n"
    "- Owner Review Responses: \" + $json.ownerResponseCount + \"\\n\\n"
    "**Pre-extracted emails (regex from all pages):** \" + JSON.stringify($json.foundEmails) + \"\\n"
    "**Pre-extracted phones (regex from all pages):** \" + JSON.stringify($json.foundPhones) + \"\\n\\n"
    "**Reviews (last 20):**\\n\" + $json.reviewTexts + \"\\n\\n"
    "**Website Text (homepage + footer + contact + about):**\\n\" + $json.websiteText + \"\\n\\n"
    "Respond with ONLY a valid JSON object, no markdown, no explanation:\\n"
    "{\\n"
    "  \\\"score\\\": <1-10>,\\n"
    "  \\\"reason\\\": \\\"<one sentence explaining the score>\\\",\\n"
    "  \\\"painSignal\\\": \\\"<specific pain point or null>\\\",\\n"
    "  \\\"emailAngle\\\": \\\"<suggested angle for Email 1>\\\",\\n"
    "  \\\"ownerFirstName\\\": \\\"<extracted first name or null>\\\",\\n"
    "  \\\"ownerLastName\\\": \\\"<extracted last name or null>\\\",\\n"
    "  \\\"email\\\": \\\"<best business email from pre-extracted list or null>\\\",\\n"
    "  \\\"phone\\\": \\\"<best phone from pre-extracted list or null>\\\"\\n"
    "}"
)

new_json_body = (
    '={{ JSON.stringify({\n'
    '  "model": "claude-haiku-4-5-20251001",\n'
    '  "max_tokens": 1500,\n'
    '  "messages": [\n'
    '    {\n'
    '      "role": "user",\n'
    '      "content": "' + new_claude_content + '"\n'
    '    }\n'
    '  ]\n'
    '}) }}'
)

# Apply changes
for n in wf['nodes']:
    if n['name'] == 'Combine Data':
        n['parameters']['jsCode'] = new_combine_code
        sys.stderr.write('Updated Combine Data\n')
    if n['name'] == 'Claude ICP Scoring':
        n['parameters']['jsonBody'] = new_json_body
        sys.stderr.write('Updated Claude prompt\n')

# Build safe payload
safe = {
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {
        k: v for k, v in wf.get("settings", {}).items()
        if k not in ["availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"]
    }
}

sys.stdout.buffer.write(json.dumps(safe, ensure_ascii=True).encode('ascii'))
