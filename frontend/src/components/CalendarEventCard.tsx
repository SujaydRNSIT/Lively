import React, { useState } from 'react';
import { Calendar, Clock, Video, CheckCircle, ExternalLink, UserCheck, ShieldCheck, Copy, Check, MailCheck, Send, RefreshCw, Mail } from 'lucide-react';
import { sendMeetingInvite } from '../services/api';

interface CalendarEventCardProps {
  channelName: string;
  demoData?: {
    meeting_id?: string;
    status?: string;
    time?: string;
    email?: string;
    topic?: string;
    host?: string;
    meeting_link?: string;
    google_calendar_link?: string;
    booked_at?: number;
  } | null;
  onInviteSent?: (email: string) => void;
}

export const CalendarEventCard: React.FC<CalendarEventCardProps> = ({
  channelName,
  demoData,
  onInviteSent
}) => {
  const meetingTime = demoData?.time || "Tomorrow at 2:00 PM EST";
  const userStoredEmail = typeof window !== 'undefined' ? localStorage.getItem('lively_user_email') || '' : '';
  const initialRecipient = (demoData?.email && demoData.email !== "prospect@example.com" && demoData.email !== "alex.rivera@nextgen.ai")
    ? demoData.email
    : userStoredEmail || demoData?.email || "";

  const [recipientEmail, setRecipientEmail] = useState<string>(initialRecipient);
  const [copied, setCopied] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [sendStatus, setSendStatus] = useState<{ success?: boolean; message?: string } | null>(null);

  const meetingLink = demoData?.meeting_link || "https://meet.google.com/new";
  const topic = demoData?.topic || "Lively Real-Time Voice AI Sales Deep-Dive";
  const host = demoData?.host || "Senior Solutions Architect";

  // Pre-fill Google Calendar web blocking URL
  const googleCalendarLink = demoData?.google_calendar_link || 
    `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(`Lively AI Demo: ${topic}`)}&details=${encodeURIComponent(`Product Walkthrough with ${host}.\nGoogle Meet: ${meetingLink}\n\nAgenda:\n1. Live Sub-300ms RTC Voice Demo\n2. Objection Handling & RAG Architecture\n3. Enterprise CRM & Live Handoffs`)}&location=${encodeURIComponent(meetingLink)}`;

  // Pre-fill Gmail direct compose URL fallback
  const gmailComposeUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(recipientEmail || 'you@company.com')}&su=${encodeURIComponent(`Confirmed: Lively AI Demo on ${meetingTime}`)}&body=${encodeURIComponent(`Hello,\n\nYour product walkthrough is scheduled for ${meetingTime}.\n\nGoogle Meet Link: ${meetingLink}\nAdd to Google Calendar: ${googleCalendarLink}\n\nHost: ${host}\nTopic: ${topic}\n\n- The Lively AI Team`)}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(meetingLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleManualSendInvite = async () => {
    let emailToSend = recipientEmail.trim();
    if (!emailToSend || !emailToSend.includes('@')) {
      const prompted = window.prompt("Please enter your email address to receive the calendar invite:", userStoredEmail);
      if (!prompted || !prompted.includes('@')) return;
      emailToSend = prompted.trim();
      setRecipientEmail(emailToSend);
      if (typeof window !== 'undefined') {
        localStorage.setItem('lively_user_email', emailToSend);
      }
    }

    setIsSending(true);
    setSendStatus(null);
    try {
      const res = await sendMeetingInvite(channelName, emailToSend, meetingTime, meetingLink);
      setIsSending(false);
      setSendStatus({
        success: true,
        message: res.delivered 
          ? `Direct email dispatched to ${emailToSend} via SMTP!` 
          : `Invite generated for ${emailToSend}! If not in inbox, click 'Add to Google Calendar' below.`
      });
      if (onInviteSent) onInviteSent(emailToSend);
    } catch (err: any) {
      setIsSending(false);
      setSendStatus({
        success: false,
        message: err.message || "Failed to trigger email. Use 'Add to Google Calendar' or 'Open Gmail'."
      });
    }
  };

  return (
    <div className="rounded-2xl border hairline bg-[#fdfdfb] dark:bg-[#121623] p-5 shadow-xs transition-colors">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b hairline">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#6166cf]/10 text-[#6166cf] border hairline">
            <Calendar className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="editorial-mono text-[9.5px] uppercase tracking-[0.16em] font-semibold text-[#6166cf]">
                Confirmed Event
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-[#10b981]/10 px-2 py-0.5 text-[9px] font-semibold text-[#10b981] border border-[#10b981]/20">
                <CheckCircle className="h-2.5 w-2.5" />
                Scheduled by AI
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[#20201e] dark:text-[#f1f0ea] mt-0.5">
              {topic}
            </h3>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          <a
            href={googleCalendarLink}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#6166cf]/30 bg-[#6166cf]/10 hover:bg-[#6166cf]/20 text-[#6166cf] text-xs font-semibold shadow-xs transition cursor-pointer"
            title="Block this event directly on your Google Calendar"
          >
            <Calendar className="h-3.5 w-3.5" />
            <span>Add to Calendar</span>
            <ExternalLink className="h-2.5 w-2.5" />
          </a>

          <a
            href={meetingLink}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#6166cf] hover:bg-[#5257be] text-white text-xs font-semibold shadow-xs transition-transform active:scale-95 cursor-pointer"
          >
            <Video className="h-3.5 w-3.5" />
            <span>Join Google Meet</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 py-3 text-xs">
        <div className="flex items-center gap-2 text-[#4c4b46] dark:text-[#9aa0ad]">
          <Clock className="h-4 w-4 text-[#6166cf] shrink-0" />
          <span><strong>Time:</strong> {meetingTime}</span>
        </div>
        <div className="flex items-center gap-2 text-[#4c4b46] dark:text-[#9aa0ad]">
          <UserCheck className="h-4 w-4 text-[#6166cf] shrink-0" />
          <span><strong>Host:</strong> {host}</span>
        </div>
        <div className="flex items-center gap-2 text-[#4c4b46] dark:text-[#9aa0ad]">
          <ShieldCheck className="h-4 w-4 text-[#10b981] shrink-0" />
          <span><strong>Format:</strong> 30-min Video Bridge</span>
        </div>
      </div>

      {/* Meet Link & Automated Dispatch Notice */}
      <div className="mt-3 pt-3 border-t hairline bg-[#f7f6f0] dark:bg-[#181d2c] p-3.5 rounded-xl">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-7 w-7 rounded-lg bg-[#10b981]/15 text-[#10b981] flex items-center justify-center shrink-0">
              <MailCheck className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-[#20201e] dark:text-[#f1f0ea] truncate">
                Target Email: <span className="font-semibold text-[#6166cf]">{recipientEmail || userStoredEmail || 'Enter your email'}</span>
              </p>
              <p className="text-[11px] text-[#77756e] dark:text-[#9aa0ad] truncate">
                Click below to add to Google Calendar or dispatch email invitation
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 flex-wrap sm:flex-nowrap">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#4c4b46] dark:text-[#d1d5db] hover:bg-[#f3f2eb] dark:hover:bg-[#1e2436] transition cursor-pointer"
            >
              {copied ? <Check className="h-3 w-3 text-[#10b981]" /> : <Copy className="h-3 w-3 text-[#6166cf]" />}
              <span>{copied ? 'Copied' : 'Copy Link'}</span>
            </button>

            <button
              onClick={handleManualSendInvite}
              disabled={isSending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#6166cf] hover:bg-[#6166cf]/10 transition cursor-pointer disabled:opacity-50"
            >
              {isSending ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
              <span>{isSending ? 'Sending...' : 'Send to My Email'}</span>
            </button>

            <a
              href={gmailComposeUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#ea4335] hover:bg-[#ea4335]/10 transition cursor-pointer"
              title="Open pre-composed email in Gmail"
            >
              <Mail className="h-3 w-3" />
              <span>Gmail</span>
            </a>
          </div>
        </div>

        {sendStatus && (
          <div className={`mt-2.5 p-2 rounded-lg text-xs flex items-center justify-between gap-2 ${
            sendStatus.success ? 'bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20' : 'bg-[#ef4444]/10 text-[#ef4444] border border-[#ef4444]/20'
          }`}>
            <span>{sendStatus.message}</span>
            <button onClick={() => setSendStatus(null)} className="text-[10px] font-bold underline cursor-pointer">dismiss</button>
          </div>
        )}
      </div>
    </div>
  );
};
