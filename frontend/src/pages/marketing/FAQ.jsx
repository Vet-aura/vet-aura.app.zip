import MarketingShell from "@/components/MarketingShell";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

const FAQS = [
  { q: "Is Vetaura making decisions for me?", a: "No. Vetaura writes DRAFTS — SOAP notes, discharge instructions, differential checklists and reply suggestions. Nothing enters the medical record or leaves the clinic without a clinician reviewing and signing. Confidence and flags are shown on every draft." },
  { q: "Where does the audio go?", a: "Audio is streamed to OpenAI Whisper for transcription and immediately discarded. Only the text transcript is kept in your clinic's private database (scoped by clinic_id) and only if you save the note." },
  { q: "Which AI models power Vetaura?", a: "Claude Sonnet 5 (Anthropic) for structured clinical drafting and OpenAI Whisper for speech-to-text. Every interaction is logged in your audit trail." },
  { q: "Can I try before I buy?", a: "Yes — 14 days free, no card required. Sign up, seed your clinic with sample patients, and try the ambient scribe on real recordings or a built-in sample transcript." },
  { q: "How is billing handled?", a: "Stripe. You can upgrade, downgrade or cancel at any time from the in-app Billing screen. Invoices and receipts are emailed automatically." },
  { q: "Which languages do owner discharges support?", a: "English, Spanish, French, German, Mandarin and Portuguese out of the box. The clinical plan you approve is preserved — Vetaura just re-writes it in the owner's language and 6th-grade reading level." },
  { q: "Does Vetaura integrate with my PIMS?", a: "Today, we support one-click CSV export and structured copy for pasting into eVetPractice, Cornerstone, AVImark and DVMax. Native integrations are on the roadmap — talk to us if you need one." },
  { q: "Who owns the data?", a: "You do. Every clinic's data is isolated by clinic_id, exportable to CSV at any time, and deletable on request." },
  { q: "What happens if I cancel?", a: "Your service continues until the end of the current billing cycle. You can export all data as CSV any time, including after cancellation." },
];

export default function FAQ() {
  return (
    <MarketingShell>
      <section className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center">
          <div className="text-xs uppercase tracking-widest text-emerald-700 font-semibold">FAQ</div>
          <h1 className="mt-2 font-serif-display text-4xl sm:text-5xl font-semibold text-emerald-950 tracking-tight">Answers.</h1>
        </div>

        <Accordion type="single" collapsible className="mt-10">
          {FAQS.map((f, i) => (
            <AccordionItem value={`item-${i}`} key={i} data-testid={`faq-${i}`}>
              <AccordionTrigger className="text-left font-semibold text-emerald-950 hover:text-emerald-800">{f.q}</AccordionTrigger>
              <AccordionContent className="text-slate-600 leading-relaxed">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </MarketingShell>
  );
}
