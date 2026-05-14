const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, TableOfContents,
  LevelFormat, ExternalHyperlink
} = require('docx');
const fs = require('fs');

// ── colour palette ──────────────────────────────────────────────────────────
const BLUE      = '1F5C99';   // headings / table headers
const LIGHTBLUE = 'D6E4F0';   // table header fill
const YELLOW    = 'FFF3CD';   // "why?" box fill
const YELLOW_BD = 'E6AC00';   // "why?" box border
const GREEN     = 'D4EDDA';   // checklist done-ish highlight
const GREY      = 'F2F2F2';   // alternating row
const WHITE     = 'FFFFFF';

const PAGE_W    = 12240;      // 8.5 in
const PAGE_H    = 15840;      // 11 in
const MARGIN    = 1080;       // 0.75 in
const CONTENT_W = PAGE_W - MARGIN * 2;   // 10080 DXA

// ── helpers ─────────────────────────────────────────────────────────────────

function b(text, size) {
  return new TextRun({ text, bold: true, size: size || 22 });
}
function t(text, opts) {
  return new TextRun({ text, size: 22, ...opts });
}
function para(children, opts) {
  if (typeof children === 'string') children = [t(children)];
  return new Paragraph({ children, spacing: { after: 120 }, ...opts });
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 36, color: WHITE, font: 'Arial' })],
    shading: { fill: BLUE, type: ShadingType.CLEAR },
    spacing: { before: 400, after: 200 },
    indent: { left: 120, right: 120 },
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 28, color: BLUE, font: 'Arial' })],
    spacing: { before: 300, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BLUE } },
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 24, color: '2E5F8C', font: 'Arial' })],
    spacing: { before: 200, after: 80 },
  });
}
function bullet(text, level) {
  if (typeof text === 'string') text = [t(text)];
  return new Paragraph({
    numbering: { reference: 'bullets', level: level || 0 },
    children: text,
    spacing: { after: 80 },
  });
}
function numbered(text) {
  if (typeof text === 'string') text = [t(text)];
  return new Paragraph({
    numbering: { reference: 'numbers', level: 0 },
    children: text,
    spacing: { after: 80 },
  });
}
function spacer(n) {
  return new Paragraph({ children: [t('')], spacing: { after: n || 160 } });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// cell border helper
const cellBorder = (color) => {
  const s = { style: BorderStyle.SINGLE, size: 4, color: color || 'CCCCCC' };
  return { top: s, bottom: s, left: s, right: s };
};

// Simple 2-col table: [[label, value], ...]
function twoColTable(rows, w1, w2) {
  w1 = w1 || 3200;
  w2 = w2 || (CONTENT_W - w1);
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [w1, w2],
    rows: rows.map(([label, value], i) =>
      new TableRow({
        children: [
          new TableCell({
            borders: cellBorder('CCCCCC'),
            width: { size: w1, type: WidthType.DXA },
            shading: { fill: i === 0 ? LIGHTBLUE : GREY, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 140, right: 140 },
            children: [para([b(label, 22)])],
          }),
          new TableCell({
            borders: cellBorder('CCCCCC'),
            width: { size: w2, type: WidthType.DXA },
            shading: { fill: WHITE, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 140, right: 140 },
            children: [para(typeof value === 'string' ? [t(value)] : value)],
          }),
        ],
      })
    ),
  });
}

// Header table: blue header row + data rows
function headerTable(headers, dataRows, colWidths) {
  const total = colWidths.reduce((a, b) => a + b, 0);
  const makeCell = (text, fill, border, bold, colW) =>
    new TableCell({
      borders: cellBorder(border || 'CCCCCC'),
      width: { size: colW, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 140, right: 140 },
      children: [para(bold
        ? [new TextRun({ text, bold: true, size: 20, color: bold === 'white' ? WHITE : '000000' })]
        : [t(text, { size: 20 })])],
    });

  const hRow = new TableRow({
    children: headers.map((h, i) => makeCell(h, BLUE, BLUE, 'white', colWidths[i])),
  });
  const dRows = dataRows.map((row, ri) =>
    new TableRow({
      children: row.map((cell, ci) =>
        makeCell(cell, ri % 2 === 0 ? WHITE : GREY, 'CCCCCC', false, colWidths[ci])
      ),
    })
  );
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [hRow, ...dRows],
  });
}

// "Why?" callout box (single-cell table)
function whyBox(title, bullets_list) {
  const children = [
    para([new TextRun({ text: title, bold: true, size: 22, color: '6D4C00' })]),
    ...bullets_list.map(item => {
      if (typeof item === 'string') {
        return new Paragraph({
          numbering: { reference: 'why-bullets', level: 0 },
          children: [t(item, { size: 20 })],
          spacing: { after: 60 },
        });
      }
      return new Paragraph({
        numbering: { reference: 'why-bullets', level: 0 },
        children: item.map(r => r),
        spacing: { after: 60 },
      });
    }),
  ];
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders: {
              top: { style: BorderStyle.SINGLE, size: 6, color: YELLOW_BD },
              bottom: { style: BorderStyle.SINGLE, size: 6, color: YELLOW_BD },
              left: { style: BorderStyle.THICK, size: 12, color: YELLOW_BD },
              right: { style: BorderStyle.SINGLE, size: 6, color: YELLOW_BD },
            },
            width: { size: CONTENT_W, type: WidthType.DXA },
            shading: { fill: YELLOW, type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 200, right: 200 },
            children,
          }),
        ],
      }),
    ],
  });
}

// Step table: number, name, description
function stepsTable(steps) {
  const W = [500, 2400, CONTENT_W - 2900];
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: W,
    rows: [
      new TableRow({
        children: ['#', 'Step Name', 'What Happens'].map((h, i) =>
          new TableCell({
            borders: cellBorder(BLUE),
            width: { size: W[i], type: WidthType.DXA },
            shading: { fill: BLUE, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [para([new TextRun({ text: h, bold: true, size: 20, color: WHITE })])],
          })
        ),
      }),
      ...steps.map(([num, name, desc], ri) =>
        new TableRow({
          children: [
            new TableCell({
              borders: cellBorder('CCCCCC'),
              width: { size: W[0], type: WidthType.DXA },
              shading: { fill: ri % 2 === 0 ? LIGHTBLUE : WHITE, type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              verticalAlign: VerticalAlign.TOP,
              children: [para([b(num, 20)])],
            }),
            new TableCell({
              borders: cellBorder('CCCCCC'),
              width: { size: W[1], type: WidthType.DXA },
              shading: { fill: ri % 2 === 0 ? LIGHTBLUE : WHITE, type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              verticalAlign: VerticalAlign.TOP,
              children: [para([b(name, 20)])],
            }),
            new TableCell({
              borders: cellBorder('CCCCCC'),
              width: { size: W[2], type: WidthType.DXA },
              shading: { fill: ri % 2 === 0 ? WHITE : GREY, type: ShadingType.CLEAR },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              verticalAlign: VerticalAlign.TOP,
              children: [para(typeof desc === 'string' ? [t(desc, { size: 20 })] : desc)],
            }),
          ],
        })
      ),
    ],
  });
}

// ── DOCUMENT ────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '•',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 560, hanging: 280 } } },
        }],
      },
      {
        reference: 'numbers',
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: '%1.',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 560, hanging: 280 } } },
        }],
      },
      {
        reference: 'why-bullets',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '▸',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 440, hanging: 220 } } },
        }],
      },
      {
        reference: 'check',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '□',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 560, hanging: 280 } } },
        }],
      },
    ],
  },
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: WHITE },
        paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: BLUE },
        paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1 },
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: '2E5F8C' },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 },
      },
    ],
  },

  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            children: [
              new TextRun({ text: 'GHL <-> Hostfully Messaging Sync -- Workflow Guide', size: 18, color: '888888', font: 'Calibri' }),
              new TextRun({ text: '\t', size: 18 }),
              new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES], size: 18, color: '888888', font: 'Calibri' }),
            ],
            tabStops: [{ type: 'right', position: CONTENT_W }],
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' } },
            spacing: { after: 80 },
          }),
        ],
      }),
      first: new Header({ children: [new Paragraph({ children: [t('')] })] }),
    },

    children: [

      // ── TITLE PAGE ─────────────────────────────────────────────────────────
      spacer(1200),
      new Paragraph({
        children: [new TextRun({ text: 'GHL <-> Hostfully', bold: true, size: 72, color: BLUE, font: 'Arial' })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Messaging Sync', bold: true, size: 72, color: BLUE, font: 'Arial' })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 240 },
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Workflow Guide', size: 40, color: '555555', font: 'Arial' })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 600 },
      }),

      // divider
      new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE } },
        spacing: { after: 400 },
        children: [t('')],
      }),

      new Paragraph({
        children: [new TextRun({ text: 'Day Drinking Properties', size: 28, color: '333333', font: 'Calibri' })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
      }),
      new Paragraph({
        children: [new TextRun({ text: 'Replacing HostBuddy with GoHighLevel Conversations', size: 24, color: '666666', font: 'Calibri' })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
      }),
      new Paragraph({
        children: [new TextRun({ text: 'May 2026', size: 22, color: '888888', font: 'Calibri' })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),

      spacer(400),

      // status box
      new Table({
        width: { size: 5000, type: WidthType.DXA },
        columnWidths: [5000],
        rows: [new TableRow({ children: [new TableCell({
          borders: cellBorder(BLUE),
          width: { size: 5000, type: WidthType.DXA },
          shading: { fill: LIGHTBLUE, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 200, right: 200 },
          children: [
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Status: Workflows Built -- Awaiting GHL Credentials', bold: true, size: 22, color: BLUE })], spacing: { after: 0 } }),
          ],
        })]})],
      }),

      pageBreak(),

      // ── TABLE OF CONTENTS ──────────────────────────────────────────────────
      new Paragraph({
        children: [new TextRun({ text: 'Table of Contents', bold: true, size: 32, color: BLUE, font: 'Arial' })],
        spacing: { before: 200, after: 200 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: BLUE } },
      }),
      new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-3' }),

      pageBreak(),

      // ── SECTION 1: OVERVIEW ────────────────────────────────────────────────
      h1('1. What Are We Building and Why?'),
      spacer(80),

      h3('The Problem'),
      para('Right now, guest messages from Airbnb, Vrbo, and Booking.com flow into Hostfully (the property management system), and a tool called HostBuddy handles AI replies. The problem is that HostBuddy is a separate system -- the team has to juggle two places to manage conversations, and there is no single view of the guest relationship.'),
      spacer(80),

      h3('The Solution'),
      para('We are connecting Hostfully and GoHighLevel (GHL) so that ALL guest messages appear inside GHL Conversations. The team (and GHL\'s AI chatbot) can read and reply directly in GHL, and the reply automatically goes back to the guest on Airbnb or wherever they are. Once this is working, HostBuddy can be switched off.'),
      spacer(80),

      h3('The Big Picture -- How It All Fits Together'),
      spacer(60),

      headerTable(
        ['System', 'Role', 'Who Sees It'],
        [
          ['Hostfully (PMS)', 'Property management hub. Receives all bookings and guest messages from Airbnb, Vrbo, Booking.com. Sends our replies back to the right channel.', 'Back-end only'],
          ['GHL Conversations', 'The single inbox where the team reads and replies to all guest messages. Also runs AI automations.', 'Team + AI'],
          ['n8n (our automation engine)', 'The "pipe" between Hostfully and GHL. 4 workflows handle the message sync automatically.', 'Engineering'],
          ['Google Sheets', 'Temporary data store used by the workflows to track which messages have been processed and which GHL contact belongs to which Hostfully thread.', 'Engineering'],
        ],
        [2200, 4880, 2080]
      ),
      spacer(120),

      h3('The 4 Workflows at a Glance'),
      spacer(60),
      headerTable(
        ['Workflow', 'Trigger', 'What It Does in One Sentence'],
        [
          ['WF-MS-1', 'Guest sends a message', 'Picks up the guest message from Hostfully and delivers it into GHL Conversations.'],
          ['WF-MS-2', 'Team / AI replies in GHL', 'Picks up the reply from GHL and sends it back through Hostfully to the guest on Airbnb / Vrbo / etc.'],
          ['WF-MS-3', 'Called by WF-MS-1 (and booking ingest)', 'Creates or updates the guest\'s contact record in GHL with booking details.'],
          ['WF-MS-4', 'Every night at 3am', 'Cleans up old tracking data in Google Sheets so the sheet does not grow forever.'],
        ],
        [2000, 2500, 4660]
      ),

      pageBreak(),

      // ── SECTION 2: WF-MS-1 ────────────────────────────────────────────────
      h1('2. WF-MS-1 -- Hostfully to GHL Inbound'),
      spacer(80),

      twoColTable([
        ['Purpose', 'Deliver guest messages from Hostfully into GHL Conversations'],
        ['Trigger', 'Hostfully calls our webhook URL when a new inbox message arrives'],
        ['n8n Workflow ID', 'V48NnUWti3fkXmYr'],
        ['Webhook URL', 'https://n8n.srv1566844.hstgr.cloud/webhook/hostfully-inbox-message'],
        ['Status', 'Built and pushed to n8n -- inactive until GHL credentials are configured'],
      ], 2400, CONTENT_W - 2400),
      spacer(120),

      h2('2.1 Step-by-Step Walkthrough'),
      spacer(60),
      para([b('Imagine a guest named Sarah books through Airbnb and sends a message: "What time is check-in?". Here is exactly what happens:')]),
      spacer(80),

      stepsTable([
        ['1', 'Webhook Receives Event', 'Hostfully sends a notification to our n8n URL the moment Sarah\'s message lands in Hostfully\'s inbox. This notification contains basic info: message ID, thread ID, lead ID, and property ID -- but NOT the actual message text yet.'],
        ['2', 'Respond 200 OK Immediately', 'Before doing anything else, we instantly tell Hostfully "got it" (HTTP 200). This is important: if we wait too long before responding, Hostfully assumes something went wrong and sends the notification again, which could cause duplicate messages.'],
        ['3', 'Agency Check', 'Hostfully serves many different property management companies. This step checks: is this event meant for us? We compare the "agency UID" in the notification against our own ID. If it belongs to someone else, we silently ignore it and stop.'],
        ['4', 'Event Type Filter', 'Hostfully sends notifications for many different events -- new bookings, updated bookings, check-outs, etc. Here we filter to ONLY process "NEW_INBOX_MESSAGE" events. Everything else is ignored.'],
        ['5', 'Build Dedup Key', 'We create a unique fingerprint for this message: "hf:" followed by the message\'s unique ID (e.g. "hf:abc-123"). This fingerprint is used in the next step to check if we have seen this exact message before.'],
        ['6', 'Check MessageDedup Sheet', 'We look up the fingerprint in our Google Sheets "MessageDedup" tab. Hostfully sometimes sends the same notification more than once (e.g. after a network blip). This check catches those duplicates.'],
        ['7', 'Stop if Already Processed', 'If the fingerprint is already in the sheet, the message was already delivered to GHL. We stop here. Nothing happens. No duplicate.'],
        ['8', 'Fetch Full Message', 'The webhook notification only had metadata. Now we call the Hostfully API to fetch the actual message text: "What time is check-in?"'],
        ['9', 'Unwrap Message', 'Hostfully\'s API wraps the response in an extra layer: { "message": { ...actual data... } }. This step unwraps it so downstream steps can use the fields directly.'],
        ['10', 'Direction Filter (GUEST_TO_HOST only)', 'We check: did this message come FROM the guest or FROM the host? We only want guest messages. Host messages (our own replies sent through GHL) are ignored here -- otherwise we would create an infinite loop where our own replies keep coming back into GHL as new messages.'],
        ['11', 'Check ThreadContactMap Cache', 'We look in our Google Sheets "ThreadContactMap" tab to see if we already know the GHL contact ID for this thread. A "thread" is the conversation thread for this reservation. If Sarah has messaged before during this stay, her thread-to-contact mapping is already cached.'],
        ['12a', 'Use Cached Contact (fast path)', 'If the cache has a match, we use the cached GHL contact ID directly and move on. No extra API calls needed.'],
        ['12b', 'Fetch Lead + Call WF-MS-3 (slow path)', 'If no cache match, we fetch Sarah\'s full lead details from Hostfully (name, email, phone, booking dates, channel, property), then call WF-MS-3 (see Section 4) to create or update her contact in GHL. Once done, we have her GHL contact ID.'],
        ['13', 'Merge Paths', 'Whether we took the cached path (12a) or the fresh lookup path (12b), both paths join back together here. From this point on, we always have a GHL contact ID to work with.'],
        ['14', 'Post Message to GHL', 'We send the message to GHL\'s Conversations API as an "inbound" message on Sarah\'s contact. GHL displays it in the Conversations inbox. The team and/or AI can now see "What time is check-in?" and respond.'],
        ['15', 'Record in MessageDedup', 'We write "hf:abc-123" into the MessageDedup sheet with the current timestamp. Any future duplicate notifications for this same message will be caught in step 6.'],
        ['16', 'Update ThreadContactMap', 'We write (or update) the mapping: "this Hostfully thread ID belongs to this GHL contact ID." Next time Sarah messages on the same reservation, step 11 will find this entry and skip the API lookup entirely.'],
      ]),
      spacer(160),

      h2('2.2 Key Design Decisions'),
      spacer(60),

      whyBox('Why do we acknowledge ("200 OK") before processing?', [
        'Hostfully has a short timeout for webhook delivery. If we do all our processing (API calls, sheet lookups) BEFORE responding, we might exceed that timeout and Hostfully will mark the delivery as failed and retry -- sending the same notification again. By responding immediately and processing afterwards, we avoid this problem.',
      ]),
      spacer(120),
      whyBox('Why the direction filter (GUEST_TO_HOST only)?', [
        'When the team replies in GHL, WF-MS-2 sends that reply to Hostfully. Hostfully then fires a NEW_INBOX_MESSAGE event for that reply. Without the direction filter, WF-MS-1 would pick up that host reply, send it BACK to GHL as an inbound message, which could trigger another reply... creating an infinite loop of messages.',
        'The fix is simple: only forward messages where direction = "GUEST_TO_HOST". Host-originated messages are dropped.',
      ]),
      spacer(120),
      whyBox('Why cache the thread-to-contact mapping in Google Sheets?', [
        'Each guest message without the cache would require: (1) call Hostfully API to get lead details, (2) call GHL API to search for the contact. That is 2 API calls per message.',
        'With the cache, it is 1 Google Sheets lookup. Much faster, and reduces API quota usage significantly for high-volume properties.',
        'The cache is updated every time a contact is looked up, so it stays fresh.',
      ]),
      spacer(120),
      whyBox('Why deduplicate messages?', [
        'Hostfully (like most webhook systems) guarantees "at least once" delivery, not "exactly once." A network hiccup can cause the same webhook to be sent 2-3 times. Without deduplication, Sarah\'s question could appear in GHL twice -- confusing the team and potentially triggering the AI to reply twice.',
      ]),

      pageBreak(),

      // ── SECTION 3: WF-MS-2 ────────────────────────────────────────────────
      h1('3. WF-MS-2 -- GHL to Hostfully Outbound'),
      spacer(80),

      twoColTable([
        ['Purpose', 'Send replies typed in GHL back through Hostfully to the guest on Airbnb / Vrbo / etc.'],
        ['Trigger', 'GHL calls our webhook URL whenever a message is sent on a Hostfully-channel contact'],
        ['n8n Workflow ID', 'r5j1PIqoMKTfLGWo'],
        ['Webhook URL', 'https://n8n.srv1566844.hstgr.cloud/webhook/ghl-outbound-message'],
        ['Status', 'Built and pushed to n8n -- inactive until GHL credentials are configured'],
      ], 2400, CONTENT_W - 2400),
      spacer(120),

      h2('3.1 Step-by-Step Walkthrough'),
      spacer(60),
      para([b('Continuing the example: the team (or AI) in GHL types "Check-in is at 3pm!" and hits send. Here is what happens:')]),
      spacer(80),

      stepsTable([
        ['1', 'Webhook Receives Event', 'GHL fires a notification to our n8n URL: "a message was sent on this contact." The notification includes the message text, the contact ID, and a message ID.'],
        ['2', 'Verify Signature', 'GHL cryptographically signs every webhook it sends. We verify that signature to confirm the request is genuinely from GHL and has not been tampered with. During initial testing, this check can be set to "skip" mode via an environment variable. For production, it is always enforced.'],
        ['3', 'Respond 200 OK Immediately', 'Same as WF-MS-1 -- we acknowledge receipt immediately so GHL does not retry.'],
        ['4', 'Extract Payload', 'We pull out the fields we need: the GHL message ID, the GHL contact ID, and the message text ("Check-in is at 3pm!"). We also build a dedup key: "ghl:" followed by the message ID.'],
        ['5', 'Check MessageDedup Sheet', 'We check if we have already processed this outbound message. GHL can also retry webhooks if our initial acknowledgment was slow.'],
        ['6', 'Stop if Already Processed', 'Same as WF-MS-1 -- if duplicate, stop.'],
        ['7', 'Get GHL Contact', 'We call the GHL API to fetch Sarah\'s full contact record. We need it to find the Hostfully thread UID stored as a custom field on the contact.'],
        ['8', 'Extract Thread UID', 'We look through Sarah\'s custom fields for "hostfully_thread_uid." This is the Hostfully thread ID for her current reservation. It was stored there when her contact was created/updated by WF-MS-3. Without this, we would not know which Hostfully conversation to reply to.'],
        ['9', 'Send to Hostfully', 'We call the Hostfully API: POST the message to the thread. We set sendVia: "AUTO" which tells Hostfully to figure out the right channel -- if Sarah is on Airbnb, send it via the Airbnb API; if she is on Vrbo, use Vrbo; etc.'],
        ['10a', 'Mark as Delivered (success)', 'If Hostfully accepted the message, we tell GHL to mark the message as "delivered." This shows a green delivery indicator in the GHL Conversations UI.'],
        ['10b', 'Mark as Failed + Log Error', 'If Hostfully rejected the message (e.g. the thread is not ready yet, or the API is down), we tell GHL to mark the message as "failed" so the team knows to check. We also write the full error details to our "MessagingErrors" Google Sheet tab so someone can investigate.'],
        ['11', 'Record in MessageDedup', 'Write "ghl:<messageId>" to the dedup sheet. Future retries of the same webhook will be caught in step 5.'],
      ]),
      spacer(160),

      h2('3.2 Key Design Decisions'),
      spacer(60),

      whyBox('Why verify the GHL webhook signature?', [
        'Our webhook URL is public -- anyone on the internet could POST data to it. Without signature verification, an attacker could send fake "send this message to the guest" requests. The Ed25519 signature from GHL proves the request came from a real GHL system.',
        'During initial setup, signature verification is set to "skip" mode so we can test without needing the full key setup. Once everything is working, it is switched to "enforce."',
      ]),
      spacer(120),
      whyBox('Why does the contact need hostfully_thread_uid stored on it?', [
        'GHL and Hostfully are two separate systems with no direct connection. The only way we know WHERE in Hostfully to send a reply is the thread UID.',
        'We store it on the GHL contact as a custom field when WF-MS-3 creates/updates the contact. Think of it as a "forwarding address" -- when a reply comes in from GHL, we look at the contact\'s address book and know exactly where to send it in Hostfully.',
      ]),
      spacer(120),
      whyBox('Why use sendVia: AUTO instead of specifying the channel?', [
        'A guest might be on Airbnb, Vrbo, Booking.com, or even direct (email/SMS). We do not store which OTA they came from in this workflow.',
        'Hostfully already knows -- the thread is linked to a specific channel. By passing "AUTO," we let Hostfully make the routing decision, which is the right system to make that call.',
      ]),
      spacer(120),
      whyBox('Why log failures to Google Sheets instead of just showing "failed" in GHL?', [
        'The GHL UI shows the message failed, but does not show WHY. The MessagingErrors sheet captures: the full error message, the exact JSON payload that was sent, and a timestamp. This makes debugging much easier -- you can see exactly what Hostfully rejected and why.',
      ]),

      pageBreak(),

      // ── SECTION 4: WF-MS-3 ────────────────────────────────────────────────
      h1('4. WF-MS-3 -- GHL Contact Upsert (Sub-Workflow)'),
      spacer(80),

      twoColTable([
        ['Purpose', 'Create or update a guest\'s contact record in GHL with their booking details from Hostfully'],
        ['Trigger', 'Called internally by WF-MS-1 (and will also be called by the Booking Ingest workflow on new bookings)'],
        ['n8n Workflow ID', 'mNQZDscqiXYetCPS'],
        ['Type', 'Sub-workflow -- not triggered by a webhook or schedule; only runs when called by another workflow'],
        ['Status', 'Built and pushed to n8n -- inactive until GHL credentials are configured'],
      ], 2400, CONTENT_W - 2400),
      spacer(120),

      h2('4.1 What Is a Sub-Workflow?'),
      para('A sub-workflow is a reusable piece of logic that other workflows can call, like a shared function. Instead of duplicating the "create or update GHL contact" logic inside both WF-MS-1 AND the booking ingest workflow, we built it once here. Both workflows call WF-MS-3 and get back a GHL contact ID. If we ever need to change how contacts are created, we change it in one place.'),
      spacer(80),

      h2('4.2 Step-by-Step Walkthrough'),
      spacer(60),

      stepsTable([
        ['1', 'Receive Input', 'Another workflow calls WF-MS-3 and passes in guest and booking data: first name, last name, email, phone, lead UID, thread UID, property UID, booking channel (Airbnb/Vrbo/etc), check-in date, check-out date.'],
        ['2', 'Normalize the Data', [
          new TextRun({ text: 'Before doing anything, we clean up the data:', size: 20 }),
          new TextRun({ text: '\n', size: 20 }),
        ]],
        ['3', 'Upsert Contact in GHL', 'We call GHL\'s "upsert" endpoint with the normalized data. GHL checks: does a contact with this email or phone already exist? If yes, it updates the existing contact. If no, it creates a new one. We also attach 6 custom fields with the booking details (see below).'],
        ['4', 'Return the Contact ID', 'We return a clean result to the calling workflow: the GHL contact ID, the thread UID, the lead UID, whether the contact was newly created or existing, and the normalized email/phone.'],
      ]),
      spacer(80),

      para([b('The 2 normalization steps (step 2 detail):')]),
      spacer(60),
      headerTable(
        ['Data', 'Problem Without Normalizing', 'What We Do'],
        [
          ['Email', '"SARAH@GMAIL.COM" and "sarah@gmail.com" would create 2 separate contacts in GHL', 'Convert to all lowercase before searching/creating'],
          ['Phone', '"555-123-4567", "(555) 123 4567", "+15551234567" are all the same number but GHL treats them as different', 'Convert to E.164 international format: +1XXXXXXXXXX'],
        ],
        [1400, 4000, 3760]
      ),
      spacer(120),

      para([b('The 6 custom fields stored on every GHL contact:')]),
      spacer(60),
      headerTable(
        ['Custom Field', 'What It Stores', 'Why It Matters'],
        [
          ['hostfully_lead_uid', 'The Hostfully unique ID for this guest\'s booking lead', 'Links the GHL contact back to the exact booking record in Hostfully'],
          ['hostfully_thread_uid', 'The Hostfully message thread ID for this reservation', 'Used by WF-MS-2 to know where to send replies -- this is the "forwarding address"'],
          ['hostfully_property_uid', 'The Hostfully property ID', 'Lets GHL automations send property-specific info (wifi codes, house rules, etc.)'],
          ['reservation_check_in', 'Check-in date', 'Enables pre-arrival automations (e.g. "Your stay starts in 3 days" message)'],
          ['reservation_check_out', 'Check-out date', 'Enables post-checkout automations and review request timing'],
          ['booking_channel', 'Airbnb / Vrbo / Booking.com / Direct', 'Lets automations handle channel-specific rules (e.g. Airbnb blocks URLs in messages)'],
        ],
        [2200, 2800, 4160]
      ),
      spacer(160),

      h2('4.3 Key Design Decisions'),
      spacer(60),

      whyBox('Why upsert instead of always creating a new contact?', [
        'A guest might book the same property twice, or book multiple properties. Without upsert, you would end up with duplicate contacts in GHL -- one per booking.',
        'GHL\'s upsert endpoint checks if a contact with the same email or phone already exists. If it does, it updates that contact with the new booking details instead of creating a duplicate.',
        'This also means the GHL contact always reflects the CURRENT booking -- the custom fields (check-in, check-out, thread UID, etc.) get updated with the latest reservation data.',
      ]),
      spacer(120),
      whyBox('Why 6 custom fields? Is that not a lot?', [
        'Each field enables real business value for automations:',
        'Check-in/out dates: send timed messages (pre-arrival tips, post-checkout review requests)',
        'Thread UID: the entire outbound reply system (WF-MS-2) depends on this',
        'Property UID: personalize messages with property-specific info',
        'Booking channel: handle platform rules (Airbnb has content restrictions that Vrbo does not)',
        'Lead UID: traceability -- you can always trace a GHL contact back to its Hostfully source',
      ]),

      pageBreak(),

      // ── SECTION 5: WF-MS-4 ────────────────────────────────────────────────
      h1('5. WF-MS-4 -- MessageDedup Daily Cleanup'),
      spacer(80),

      twoColTable([
        ['Purpose', 'Delete old entries from the MessageDedup tracking sheet so it does not grow forever'],
        ['Trigger', 'Runs automatically every night at 3:00 AM UTC (low-traffic window)'],
        ['n8n Workflow ID', 'wW21OSK8Tqe2I1ht'],
        ['Status', 'Built and pushed to n8n -- ready to activate (no GHL credentials needed)'],
      ], 2400, CONTENT_W - 2400),
      spacer(120),

      h2('5.1 Why Does This Workflow Exist?'),
      para('Every time a message passes through WF-MS-1 or WF-MS-2, we write a record into the "MessageDedup" Google Sheet. This prevents duplicate messages. But if we never clean up, the sheet will have thousands of rows after a few months, making lookups slow and wasting storage.'),
      para('WF-MS-4 runs quietly every night and removes any entries older than 7 days. After 7 days, there is zero chance Hostfully or GHL will retry that old webhook -- so the dedup record is no longer needed.'),
      spacer(80),

      h2('5.2 Step-by-Step Walkthrough'),
      spacer(60),

      stepsTable([
        ['1', 'Schedule: 3:00 AM UTC', 'The workflow is triggered automatically by a time schedule. 3am UTC is chosen because it is the lowest-traffic window for US-based properties.'],
        ['2', 'Read MessageDedup Sheet', 'We read all rows currently in the MessageDedup tab. Each row has: a message key (e.g. "hf:abc-123"), a direction (inbound/outbound), and a timestamp (createdAt).'],
        ['3', 'Compute Rows to Delete', 'We calculate which rows are older than 7 days based on the createdAt timestamp. Importantly, we sort the row numbers in REVERSE order (highest row number first). This is critical for the deletion step (see Why box below).'],
        ['4', 'Skip If Nothing to Delete', 'If no rows are older than 7 days, we skip the deletion step entirely. No unnecessary API calls to Google Sheets.'],
        ['5', 'Batch Delete Rows', 'We send a single "batchUpdate" request to the Google Sheets API that deletes ALL the old rows at once in one operation. This is faster and uses far less API quota than deleting rows one at a time.'],
      ]),
      spacer(160),

      h2('5.3 Key Design Decisions'),
      spacer(60),

      whyBox('Why 7 days and not shorter (e.g. 24 hours)?', [
        'If a webhook system retried a message, it would almost certainly do so within minutes or hours, not days. 7 days gives a very wide safety margin.',
        'Keeping records for 7 days also gives the team time to debug any issues (e.g. if you see a duplicate message, you can check the sheet and confirm it was already processed).',
      ]),
      spacer(120),
      whyBox('Why delete in reverse order (highest row number first)?', [
        'Google Sheets rows are numbered by their position. Row 1 is the header, row 2 is the first data row, etc.',
        'If you delete row 5, what was row 6 becomes row 5, row 7 becomes row 6, and so on. Every row below shifts up by one.',
        'If your deletion list says "delete rows 5, 6, 7" and you delete row 5 first, the original row 6 is now at position 5. When you try to delete "row 6," you accidentally delete what was originally row 7.',
        'Deleting from the bottom up (row 7, then 6, then 5) avoids this problem: deleting row 7 does not change the positions of rows 5 and 6.',
      ]),
      spacer(120),
      whyBox('Why batch delete instead of deleting one row at a time?', [
        'Google Sheets API has rate limits (typically 60 requests per minute). If there are 200 old rows to delete, doing them one at a time would take over 3 minutes and risk hitting rate limits.',
        'A single batchUpdate request handles all 200 deletions in one API call -- much faster and no rate limit risk.',
      ]),

      pageBreak(),

      // ── SECTION 6: GOOGLE SHEETS DATA LAYER ───────────────────────────────
      h1('6. Google Sheets Data Layer'),
      spacer(80),

      para('We use three tabs in the main "Hostfully Operations V2" Google Sheet as a lightweight database to support the messaging workflows. Here is what each one does:'),
      spacer(80),

      h2('6.1 MessageDedup Tab'),
      twoColTable([
        ['Sheet ID (gid)', '1282682083'],
        ['Purpose', 'Tracks every message that has been processed to prevent duplicates'],
        ['Managed by', 'WF-MS-1 and WF-MS-2 (write), WF-MS-4 (cleanup)'],
      ], 2400, CONTENT_W - 2400),
      spacer(80),
      headerTable(
        ['Column', 'Example Value', 'Meaning'],
        [
          ['messageKey', 'hf:a1b2c3d4-e5f6', 'Unique fingerprint for the message. "hf:" prefix = Hostfully message; "ghl:" prefix = GHL message.'],
          ['direction', 'inbound', '"inbound" = guest -> GHL. "outbound" = GHL -> guest via Hostfully.'],
          ['createdAt', '2026-05-06T14:32:11.000Z', 'When this record was created. Used by WF-MS-4 to calculate age and decide when to delete.'],
        ],
        [2200, 2800, 4160]
      ),
      spacer(160),

      h2('6.2 ThreadContactMap Tab'),
      twoColTable([
        ['Sheet ID (gid)', '1241749258'],
        ['Purpose', 'Caches the Hostfully thread UID to GHL contact ID mapping to avoid repeated API calls'],
        ['Managed by', 'WF-MS-1 (write/update)'],
      ], 2400, CONTENT_W - 2400),
      spacer(80),
      headerTable(
        ['Column', 'Example Value', 'Meaning'],
        [
          ['threadUid', 'thread-uuid-123', 'The Hostfully thread UID for the reservation\'s message conversation.'],
          ['ghlContactId', 'abc123ghl', 'The GHL contact ID for the guest.'],
          ['leadUid', 'lead-uuid-456', 'The Hostfully lead UID -- for traceability back to the original booking.'],
          ['lastSeenAt', '2026-05-06T14:32:11.000Z', 'Updated every time a message is processed for this thread. Helps identify stale mappings.'],
        ],
        [2200, 2800, 4160]
      ),
      spacer(160),

      h2('6.3 MessagingErrors Tab'),
      twoColTable([
        ['Sheet ID (gid)', '1322384176'],
        ['Purpose', 'Dead-letter queue: captures details of any message that failed to send'],
        ['Managed by', 'WF-MS-2 (writes on failure)'],
      ], 2400, CONTENT_W - 2400),
      spacer(80),
      headerTable(
        ['Column', 'Example Value', 'Meaning'],
        [
          ['direction', 'outbound', 'Which direction the failed message was going (always "outbound" for WF-MS-2 failures).'],
          ['errorMessage', 'Hostfully send failed (status 422): thread not ready', 'The error returned by Hostfully (or GHL).'],
          ['payload', '{contactId: "abc", body: "Check-in at 3pm"}', 'The full message payload that was attempted. Used to manually retry if needed.'],
          ['createdAt', '2026-05-06T14:32:11.000Z', 'When the failure occurred.'],
        ],
        [2200, 2800, 4160]
      ),

      pageBreak(),

      // ── SECTION 7: WHAT'S STILL NEEDED ────────────────────────────────────
      h1('7. What Is Still Needed Before Going Live'),
      spacer(80),

      para('All 4 workflows have been built and are sitting in n8n in an inactive state. They cannot be activated until the items below are completed. All of these require action from David (the GHL account owner) or us working together once the GHL token arrives.'),
      spacer(120),

      h2('7.1 Items Needed from David'),
      spacer(60),

      headerTable(
        ['#', 'Item', 'How to Get It', 'Blocks'],
        [
          ['1', 'GHL Private Integration Token (PIT)', 'GHL -> Settings -> Private Integrations -> Create New. Scopes needed: conversations.write, conversations/message.write, conversations/message.readonly, contacts.write, contacts.readonly', 'Everything else'],
          ['2', 'Confirm Hostfully API v3.2', 'Check: Hostfully PMP -> Settings -> API -> version. Or we test it once we have the API key.', 'WF-MS-1, WF-MS-2'],
          ['3', 'Create 6 GHL Custom Fields', 'GHL -> Settings -> Custom Fields -> Contacts. Create the 6 fields listed in Section 4.2. Then send us the field IDs (shown in the URL when editing a field).', 'WF-MS-3, WF-MS-1, WF-MS-2'],
          ['4', 'Pick first test properties', 'Choose 1-2 low-volume properties to run in shadow mode first (HostBuddy stays on as backup).', 'Phase G testing'],
          ['5', 'Conversation Provider name', 'What should the channel be called in GHL? Options: "Hostfully", "PMS Messaging", "Guest Messaging"', 'WF-MS-2 setup'],
        ],
        [280, 2300, 4200, 2380]
      ),
      spacer(160),

      h2('7.2 Steps We Do Once Token Arrives'),
      spacer(60),

      para([b('Once David provides the GHL token, here is the order of operations:')]),
      spacer(80),

      headerTable(
        ['Step', 'What We Do', 'Result'],
        [
          ['1', 'Create "GHL API" credential in n8n', 'HTTP Header Auth credential: Authorization: Bearer <token>'],
          ['2', 'Assign credential to GHL nodes', 'Open each of the 4 workflows in n8n UI and assign the new credential to the 5 GHL HTTP nodes (1 in WF-MS-3, 1 in WF-MS-1, 3 in WF-MS-2)'],
          ['3', 'Create GHL Custom Conversation Provider', 'API call to GHL with the webhook URL. Returns a conversationProviderId.'],
          ['4', 'Set environment variables in n8n', 'Add all 10 env vars to n8n Settings -> Variables (see list below)'],
          ['5', 'Register Hostfully webhook', 'POST to Hostfully API to register our new inbox-message webhook URL'],
          ['6', 'Activate WF-MS-4 first', 'No GHL dependency -- can run safely from day one'],
          ['7', 'Activate WF-MS-3', 'GHL credential needed'],
          ['8', 'Activate WF-MS-1 + WF-MS-2', 'Requires provider ID and custom field IDs to be set'],
          ['9', 'Shadow mode test (1-2 weeks)', 'HostBuddy stays ON. We verify messages flow correctly in GHL without disrupting live operations.'],
          ['10', 'Cutover', 'Disable HostBuddy on first test property. Monitor 48 hours. Roll out to remaining properties.'],
        ],
        [480, 3400, 5280]
      ),
      spacer(160),

      h2('7.3 Full List of n8n Environment Variables'),
      spacer(60),
      para('These need to be set in n8n -> Settings -> Variables before the workflows can run:'),
      spacer(60),
      headerTable(
        ['Variable Name', 'Value / Source', 'Used In'],
        [
          ['GHL_LOCATION_ID', 'RSZ3HWAGH7WnU52Zs6aW (already known)', 'WF-MS-3'],
          ['GHL_CONVERSATION_PROVIDER_ID', 'From Step 3 above (API call result)', 'WF-MS-1'],
          ['GHL_WEBHOOK_PUBLIC_KEY', 'GHL Ed25519 public key (PEM format) -- from GHL developer docs', 'WF-MS-2'],
          ['GHL_SIGNATURE_VERIFY', 'Set to "skip" during testing; change to "enforce" for production', 'WF-MS-2'],
          ['GHL_CF_HOSTFULLY_LEAD_UID', 'Custom field ID from Step 3 above', 'WF-MS-3'],
          ['GHL_CF_HOSTFULLY_THREAD_UID', 'Custom field ID from Step 3 above', 'WF-MS-2, WF-MS-3'],
          ['GHL_CF_HOSTFULLY_PROPERTY_UID', 'Custom field ID from Step 3 above', 'WF-MS-3'],
          ['GHL_CF_RESERVATION_CHECK_IN', 'Custom field ID from Step 3 above', 'WF-MS-3'],
          ['GHL_CF_RESERVATION_CHECK_OUT', 'Custom field ID from Step 3 above', 'WF-MS-3'],
          ['GHL_CF_BOOKING_CHANNEL', 'Custom field ID from Step 3 above', 'WF-MS-3'],
        ],
        [3200, 3400, 2560]
      ),

      pageBreak(),

      // ── SECTION 8: QUICK REFERENCE ────────────────────────────────────────
      h1('8. Quick Reference'),
      spacer(80),

      h2('8.1 All Workflow IDs'),
      spacer(60),
      headerTable(
        ['Workflow', 'n8n ID', 'Webhook / Trigger'],
        [
          ['WF-MS-1 -- Hostfully -> GHL Inbound', 'V48NnUWti3fkXmYr', '/webhook/hostfully-inbox-message'],
          ['WF-MS-2 -- GHL -> Hostfully Outbound', 'r5j1PIqoMKTfLGWo', '/webhook/ghl-outbound-message'],
          ['WF-MS-3 -- GHL Contact Upsert', 'mNQZDscqiXYetCPS', 'Sub-workflow (called internally)'],
          ['WF-MS-4 -- MessageDedup Cleanup', 'wW21OSK8Tqe2I1ht', 'Schedule: daily 03:00 UTC'],
        ],
        [3200, 2400, 3560]
      ),
      spacer(120),

      h2('8.2 Google Sheets Tabs'),
      spacer(60),
      headerTable(
        ['Tab Name', 'Sheet gid', 'Purpose'],
        [
          ['MessageDedup', '1282682083', 'Tracks processed messages to prevent duplicates (7-day TTL)'],
          ['ThreadContactMap', '1241749258', 'Cache: Hostfully thread UID -> GHL contact ID'],
          ['MessagingErrors', '1322384176', 'Dead-letter queue: failed message send attempts'],
        ],
        [2400, 1600, 5160]
      ),
      spacer(120),

      h2('8.3 n8n Base URL'),
      para([b('Cloud n8n: '), t('https://n8n.srv1566844.hstgr.cloud')]),
      para([b('Local n8n: '), t('http://localhost:5678')]),

      spacer(200),

      // footer note
      new Paragraph({
        children: [new TextRun({ text: 'This document covers workflows WF-MS-1 through WF-MS-4. The Hostfully Booking Ingest workflow (WF1) will also be updated in a later phase (Phase F) to call WF-MS-3 on every new booking -- this is not yet implemented.', size: 18, color: '888888', italics: true })],
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' } },
        spacing: { before: 200 },
      }),

    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('C:/folderF/n8n-workspace/docs/messaging-sync/workflow-explainer.docx', buffer);
  console.log('Done: workflow-explainer.docx written successfully');
}).catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
