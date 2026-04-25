import json, sys

with open('workflows/drafts/cold-email/CE1-lead-qualification.json', 'rb') as f:
    wf = json.loads(f.read().decode('utf-8', errors='replace'))

# ── Combine Data: better noise stripping + dedup ──────────────────────────────
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

const emailMatches = [...new Set(
  (allRaw.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g) || [])
  .filter(e => !e.match(/\.(png|jpg|jpeg|gif|svg|webp|css|js)$/i))
)];

const phoneMatches = [...new Set(
  (allRaw.match(/\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}/g) || [])
  .map(p => p.trim())
)];

// ── NOISE STRIPPING ─────────────────────────────────────────────────────────
const BOILERPLATE = /cookie policy|privacy policy|terms of service|all rights reserved|©\s*\d{4}|back to top|skip to content|subscribe to our|sign up for our newsletter|follow us on|powered by|unsubscribe/i;

const stripNoise = (text) => {
  const lines = text
    .replace(/!\[.*?\]\(.*?\)/g, '')                        // remove image markdown ![alt](url)
    .replace(/\[([^\]]{1,60})\]\(https?:\/\/[^\)]+\)/g, '$1') // [text](url) → text (keep label)
    .replace(/^https?:\/\/\S+$/gm, '')                      // remove bare URL-only lines
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')         // HTML entities
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .split('\n');

  return lines
    .filter(line => {
      const t = line.trim();
      if (!t) return true;                                   // keep blanks for paragraph spacing
      if (BOILERPLATE.test(t)) return false;                 // remove boilerplate
      // Remove single nav-style words (Home, Services, Contact, Blog…)
      const words = t.split(/\s+/).filter(Boolean);
      if (words.length === 1 && t.length < 20) return false;
      return true;
    })
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};

// ── DEDUPLICATION across pages ──────────────────────────────────────────────
// Track paragraphs already seen (by first 80 chars) so repeated header/footer
// content on every page doesn't consume Claude's context window.
const seenKeys = new Set();

const dedup = (text) => {
  return text.split('\n\n')
    .filter(para => {
      const key = para.trim().substring(0, 80);
      if (key.length < 40) return true;        // keep short chunks (addresses, labels)
      if (seenKeys.has(key)) return false;     // duplicate — skip
      seenKeys.add(key);
      return true;
    })
    .join('\n\n');
};

const homepageClean = dedup(stripNoise(homepageRaw));
const contactClean  = dedup(stripNoise(contactRaw));
const aboutClean    = dedup(stripNoise(aboutRaw));

// ── ASSEMBLE with section labels ────────────────────────────────────────────
// Homepage: first 2000 chars + last 500 (footer area has contacts/emails)
const homepageHead = homepageClean.substring(0, 2000);
const homepageTail = homepageClean.length > 2500
  ? '\n--- footer ---\n' + homepageClean.slice(-500)
  : '';

// Contact page: up to 1500 chars (skip if it's the same as homepage — some sites duplicate)
const contactSection = (contactClean && contactClean.substring(0, 80) !== homepageClean.substring(0, 80))
  ? contactClean.substring(0, 1500)
  : '';

// About page: up to 5000 chars
const aboutSection = aboutClean.substring(0, 5000);

const websiteText = [
  '=== HOMEPAGE ===',
  homepageHead + homepageTail,
  contactSection ? '=== CONTACT PAGE ===' : '',
  contactSection,
  aboutSection ? '=== ABOUT PAGE ===' : '',
  aboutSection
].filter(Boolean).join('\n\n');

return [{ json: {
  ...prev,
  websiteText,
  foundEmails: emailMatches,
  foundPhones: phoneMatches
} }];"""

# ── Claude prompt: XML structure, same scoring rules, cleaner format ──────────
# Build the content string carefully — n8n expression interpolates $json.*
claude_content = (
    "You are an ICP scoring engine and contact extractor for Zelvop — "
    "scheduling, dispatch, and operations software for cleaning companies.\\n\\n"
    "Do TWO things and return a single JSON object.\\n\\n"
    "TASK 1 — ICP Score (1-10):\\n"
    "HIGH weight:\\n"
    "- Team size signals: mentions of crew, multiple cleaners, 'our team' = higher score. Solo operator = lower.\\n"
    "- Booking method: WhatsApp/phone-only = manual pain (good). Existing online booking system = lower need.\\n"
    "- Airbnb/vacation rental cleaning = high score (proven Zelvop use case).\\n"
    "- Franchise or chain brand = auto-disqualify, score 1.\\n"
    "MEDIUM weight:\\n"
    "- Review count sweet spot: 40-80 (established but not enterprise). Under 20 = too small. Over 150 = likely too big.\\n"
    "- Owner personally responds to reviews = decision maker is accessible.\\n\\n"
    "TASK 2 — Best contact (pick from pre-extracted lists only):\\n"
    "- email: from the emails list — prefer hello@, info@, or name-based. Ignore noreply@, support@.\\n"
    "- phone: from the phones list — pick the main business number.\\n"
    "- ownerFirstName / ownerLastName: look in About page and review responses for founder/owner name.\\n\\n"
    "<lead>\\n"
    "  <business>\\n"
    "    <name>\" + $json.businessName + \"</name>\\n"
    "    <city>\" + $json.city + \"</city>\\n"
    "    <category>\" + $json.category + \"</category>\\n"
    "    <rating>\" + $json.totalScore + \"</rating>\\n"
    "    <review_count>\" + $json.reviewsCount + \"</review_count>\\n"
    "    <has_online_booking>\" + $json.hasBookingLink + \"</has_online_booking>\\n"
    "    <owner_response_count>\" + $json.ownerResponseCount + \"</owner_response_count>\\n"
    "  </business>\\n\\n"
    "  <pre_extracted_contacts>\\n"
    "    <emails>\" + JSON.stringify($json.foundEmails) + \"</emails>\\n"
    "    <phones>\" + JSON.stringify($json.foundPhones) + \"</phones>\\n"
    "  </pre_extracted_contacts>\\n\\n"
    "  <customer_reviews>\\n"
    "\" + $json.reviewTexts + \"\\n"
    "  </customer_reviews>\\n\\n"
    "  <website_content>\\n"
    "\" + $json.websiteText + \"\\n"
    "  </website_content>\\n"
    "</lead>\\n\\n"
    "Return ONLY valid JSON, no markdown fences:\\n"
    "{\\n"
    "  \\\"score\\\": <1-10>,\\n"
    "  \\\"reason\\\": \\\"<one sentence>\\\",\\n"
    "  \\\"painSignal\\\": \\\"<specific pain signal or null>\\\",\\n"
    "  \\\"emailAngle\\\": \\\"<suggested angle for first outreach email>\\\",\\n"
    "  \\\"ownerFirstName\\\": \\\"<from content or null>\\\",\\n"
    "  \\\"ownerLastName\\\": \\\"<from content or null>\\\",\\n"
    "  \\\"email\\\": \\\"<from emails list or null>\\\",\\n"
    "  \\\"phone\\\": \\\"<from phones list or null>\\\"\\n"
    "}"
)

new_json_body = (
    '={{ JSON.stringify({\n'
    '  "model": "claude-haiku-4-5-20251001",\n'
    '  "max_tokens": 1500,\n'
    '  "messages": [\n'
    '    {\n'
    '      "role": "user",\n'
    '      "content": "' + claude_content + '"\n'
    '    }\n'
    '  ]\n'
    '}) }}'
)

# Apply changes
for n in wf['nodes']:
    if n['name'] == 'Combine Data':
        n['parameters']['jsCode'] = new_combine_code
        sys.stderr.write('Updated: Combine Data\n')
    if n['name'] == 'Claude ICP Scoring':
        n['parameters']['jsonBody'] = new_json_body
        sys.stderr.write('Updated: Claude ICP Scoring\n')

# Strip fields n8n rejects on PUT
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
