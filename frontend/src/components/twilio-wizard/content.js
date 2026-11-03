export const SAMPLE_MESSAGES = [
  "Meadow Ridge Vet: Hi Amelia, a reminder that Bella's rabies booster is due in 14 days. Reply or call us to book. Reply STOP to opt out.",
  "Meadow Ridge Vet: Bella's discharge instructions are ready. Give 1 tablet twice daily with food. Questions? Reply here. Reply STOP to opt out.",
  "Meadow Ridge Vet: Thanks for your message. A team member will reply shortly. If this is an emergency, call (415) 555-0100 now. Reply STOP to opt out.",
];

export const OPT_IN_TEXT =
  "Clients opt in on our intake / new-client form (checkbox: \"Text me appointment reminders and care updates\"), verbally at the front desk (recorded in our practice software), or by texting our number first. Every message identifies the clinic and includes \"Reply STOP to opt out\". HELP returns our contact info.";

export const STEP_CONTENT = {
  account: {
    title: "Create and upgrade your Twilio account",
    time: "10 min",
    why: "Your clinic owns the account, the phone number and the carrier registration, and pays Twilio directly. Vetaura never sees your billing and can be disconnected at any time.",
    steps: [
      "Sign up at twilio.com and verify your email and mobile number.",
      "Upgrade from Trial: Console → Billing → Upgrade account, then add a payment method. Trial accounts can only text verified numbers and add a \"Sent from a Twilio trial account\" prefix.",
      "Note your Account SID (starts with AC…) on the Console home page. You'll paste it in step 6.",
    ],
    links: [["Create a Twilio account", "https://www.twilio.com/try-twilio"], ["Twilio SMS pricing (US)", "https://www.twilio.com/en-us/sms/pricing/us"]],
    tip: "Typical costs (paid to Twilio, not Vetaura): a local number is about $1–2/month, each US text segment is under a cent plus carrier fees, and A2P registration has small one-time and monthly fees. Check Twilio's pricing page for current rates.",
  },
  number: {
    title: "Get a local phone number",
    time: "5 min",
    why: "Clients see this number on every text and can call it. Pick one in your clinic's area code, or bring your existing clinic number.",
    steps: [
      "Console → Phone Numbers → Manage → Buy a number.",
      "Filter by your area code and make sure SMS and Voice are both ticked.",
      "Buy the number. Want to keep your current clinic number instead? Start a port request (Phone Numbers → Port & Host). Porting usually takes 1–4 weeks.",
    ],
    links: [["Buy a number", "https://console.twilio.com/us1/develop/phone-numbers/manage/search"]],
    tip: "Once Twilio is connected, you can also search and buy numbers from Vetaura's Phone & SMS page.",
  },
  messaging_service: {
    title: "Create a Messaging Service",
    time: "5 min",
    why: "Every Vetaura text goes through a Messaging Service, so carriers can tie it to your approved A2P campaign. Texts sent outside one get filtered.",
    steps: [
      "Console → Messaging → Services → Create Messaging Service. Name it e.g. \"<Clinic name> – Vetaura\".",
      "Sender Pool → Add Senders → Phone Number → pick the number from step 2.",
      "Integration: skip for now. You'll paste Vetaura's webhook URL in step 7.",
      "Copy the Messaging Service SID (starts with MG…).",
    ],
    links: [["Messaging Services", "https://console.twilio.com/us1/develop/sms/services"]],
  },
  a2p: {
    title: "Register for A2P 10DLC (US carriers)",
    time: "20 min + review time",
    why: "US carriers require every business that texts from a 10-digit number to register a Brand (your clinic) and a Campaign (what you send). Unregistered texts get blocked. Only your clinic can do this, because it requires your legal business details.",
    steps: [
      "Console → Messaging → Regulatory Compliance → Onboarding. Create your Customer Profile (legal business name, EIN, address, authorized contact).",
      "Register a Brand. \"Low-volume Standard\" fits most single clinics; choose \"Standard\" if you send more than ~6,000 texts a day.",
      "Create a Campaign on the Messaging Service from step 3. Use case: \"Customer Care\", or \"Mixed\" if you'll send marketing blasts too.",
      "Paste the sample messages and opt-in description below. Make sure opt-out (STOP) and help (HELP) are enabled.",
      "Submit. Carrier review usually takes a few days and can take up to 2–3 weeks. Track the status in Vetaura → SMS Compliance.",
    ],
    links: [["A2P 10DLC onboarding", "https://console.twilio.com/us1/develop/sms/regulatory-compliance/a2p-10dlc-overview"], ["Twilio A2P 10DLC guide", "https://www.twilio.com/docs/messaging/compliance/a2p-10dlc"]],
    samples: true,
  },
  api_key: {
    title: "Create an API key for Vetaura",
    time: "3 min",
    why: "Vetaura connects with its own API key that you can revoke at any time. Never paste your Auth Token anywhere.",
    steps: [
      "Console → Account → API keys & tokens → Create API key.",
      "Friendly name \"Vetaura\". Key type: Restricted if your account offers it (otherwise Standard, which can still be revoked any time).",
      "For a Restricted key, allow at least: sending and reading Messages, reading Messaging Services and their phone numbers / A2P campaign, reading Incoming Phone Numbers (plus write if you want Vetaura to buy numbers), and reading Calls and Recordings (for voicemail transcription).",
      "Copy the SID (starts with SK…) and the Secret. The secret is shown only once.",
    ],
    links: [["API keys & tokens", "https://console.twilio.com/us1/account/keys-credentials/api-keys"]],
    tip: "If the connection check in the next step says a permission is missing, edit the key in Twilio and add it. You don't need a new key.",
  },
  connect: { title: "Connect and test", time: "1 min" },
  webhooks: { title: "Point Twilio at Vetaura", time: "5 min" },
};

export const STEP_LABELS = {
  account: "Twilio account", number: "Phone number", messaging_service: "Messaging Service",
  a2p: "A2P registration", api_key: "API key", connect: "Connect & test", webhooks: "Webhooks",
};
