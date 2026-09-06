import React, { useState } from 'react';
import { Calendar, Clock, Video, Mail, CheckCircle, ExternalLink, Send, UserCheck, ShieldCheck, Info, AlertCircle } from 'lucide-react';
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
  const initialEmail = (demoData?.email && demoData.email !== "prospect@example.com" && demoData.email !== "alex.rivera@nextgen.ai")
    ? demoData.email
    : userStoredEmail || demoData?.email || "";
  const meetingLink = demoData?.meeting_link || "https://meet.google.com/new";
  const topic = demoData?.topic || "Lively Real-Time Voice AI Sales Deep-Dive";
  const host = demoData?.host || "Senior Solutions Architect";

  const [emailInput, setEmailInput] = useState<string>(initialEmail);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error' | 'notice';
    message: string;
    delivered?: boolean;
  } | null>(null);

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = emailInput.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setFeedback({ type: 'error', message: 'Please enter a valid email address.' });
      return;
    }

    setIsSending(true);
    setFeedback(null);
    try {
      localStorage.setItem('lively_user_email', cleanEmail);
      const res = await sendMeetingInvite(channelName, cleanEmail, meetingTime, meetingLink);
      const wasDelivered = !!res?.delivered;
      if (wasDelivered) {
        setFeedback({
          type: 'success',
          delivered: true,
          message: `Google Meet link & Calendar block successfully delivered to ${cleanEmail} via SMTP!`
        });
      } else {
        setFeedback({
          type: 'notice',
          delivered: false,
          message: `Demo reserved in Deal State for ${cleanEmail}. Note: SMTP credentials are not yet configured in .env, so no email was sent directly to your inbox.`
        });
      }
      if (onInviteSent) onInviteSent(cleanEmail);

    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Failed to dispatch email invite.'
      });
    } finally {
      setIsSending(false);
    }
  };

  // Google Calendar URL template (uses backend generated slot dates or fallback)
  const gcalUrl = demoData?.google_calendar_link || (
    `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(topic)}&location=${encodeURIComponent(meetingLink)}&details=${encodeURIComponent(`Lively Voice AI Architecture Demo\nHost: ${host}\nGoogle Meet Bridge: ${meetingLink}`)}`
  );

  // 1-Click Gmail compose URL
  const targetEmail = emailInput.trim() || initialEmail || "";
  const gmailBody = `Hi,\n\nHere are the details for our Agora Real-Time Voice AI demonstration:\n\n• Topic: ${topic}\n• Time: ${meetingTime}\n• Host: ${host}\n• Google Meet Link: ${meetingLink}\n\nLooking forward to speaking with you!\n— Lively AI Solutions Team`;
  const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(targetEmail)}&su=${encodeURIComponent(`Confirmed: ${topic} - ${meetingTime}`)}&body=${encodeURIComponent(gmailBody)}`;
  const mailtoUrl = `mailto:${encodeURIComponent(targetEmail)}?subject=${encodeURIComponent(`Confirmed: ${topic} - ${meetingTime}`)}&body=${encodeURIComponent(gmailBody)}`;

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
                Scheduled
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[#20201e] dark:text-[#f1f0ea] mt-0.5">
              {topic}
            </h3>
          </div>
        </div>

        <a
          href={meetingLink}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6166cf] hover:bg-[#5257be] text-white text-xs font-semibold shadow-xs transition-transform active:scale-95 cursor-pointer"
        >
          <Video className="h-3.5 w-3.5" />
          <span>Join Google Meet</span>
          <ExternalLink className="h-3 w-3" />
        </a>
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

      {/* Email Invite Input Section */}
      <div className="mt-3 pt-3 border-t hairline bg-[#f7f6f0] dark:bg-[#181d2c] p-3.5 rounded-xl">
        <form onSubmit={handleSendInvite} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          <div className="relative flex-1">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8c8a82] dark:text-[#6e7587]" />
            <input
              type="email"
              placeholder="Enter your email to receive Google Meet invite..."
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              className="w-full rounded-lg border hairline bg-white dark:bg-[#101420] pl-9 pr-3 py-1.5 text-xs text-[#20201e] dark:text-[#f1f0ea] placeholder-[#8c8a82] dark:placeholder-[#6e7587] focus:outline-none focus:ring-1 focus:ring-[#6166cf]"
            />
          </div>

          <button
            type="submit"
            disabled={isSending}
            className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#20201e] dark:bg-[#f1f0ea] text-white dark:text-[#121623] text-xs font-semibold hover:opacity-90 transition disabled:opacity-50 cursor-pointer shrink-0"
          >
            <Send className="h-3 w-3" />
            <span>{isSending ? 'Dispatching...' : 'Send Google Meet Invite'}</span>
          </button>

          <a
            href={gcalUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#151926] text-xs font-medium text-[#4c4b46] dark:text-[#d1d5db] hover:bg-[#f3f2eb] dark:hover:bg-[#1e2436] transition shrink-0 cursor-pointer"
          >
            <Calendar className="h-3 w-3 text-[#6166cf]" />
            <span>+ Google Calendar</span>
          </a>
        </form>

        {/* Feedback Messages */}
        {feedback && (
          <div className="mt-3 space-y-2">
            <div
              className={`text-xs p-2.5 rounded-lg border flex items-start gap-2 ${
                feedback.type === 'success'
                  ? 'bg-[#10b981]/10 border-[#10b981]/30 text-[#059669] dark:text-[#34d399]'
                  : feedback.type === 'error'
                  ? 'bg-[#ef4444]/10 border-[#ef4444]/30 text-[#dc2626] dark:text-[#f87171]'
                  : 'bg-[#f59e0b]/10 border-[#f59e0b]/30 text-[#b45309] dark:text-[#fbbf24]'
              }`}
            >
              {feedback.type === 'success' ? (
                <CheckCircle className="h-4 w-4 shrink-0 mt-0.5" />
              ) : feedback.type === 'error' ? (
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              ) : (
                <Info className="h-4 w-4 shrink-0 mt-0.5" />
              )}
              <div className="flex-1 text-[11.5px] leading-relaxed">
                <span>{feedback.message}</span>
              </div>
            </div>

            {/* Instant 1-Click Email Fallback Links if SMTP is unconfigured */}
            {feedback.delivered === false && (
              <div className="p-3 bg-white dark:bg-[#121623] rounded-lg border hairline flex flex-wrap items-center justify-between gap-2.5">
                <div className="text-[11px] text-[#555] dark:text-[#aaa]">
                  <span>Send directly from your mailbox with 1 click:</span>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={gmailUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-[#ea4335] hover:bg-[#d93025] text-white text-[11px] font-semibold transition shadow-xs cursor-pointer"
                  >
                    <Mail className="h-3 w-3" />
                    <span>Open in Gmail</span>
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>

                  <a
                    href={mailtoUrl}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border hairline bg-[#f7f6f0] dark:bg-[#1a2030] text-[#333] dark:text-[#ddd] text-[11px] font-medium hover:bg-[#ebe9df] transition cursor-pointer"
                  >
                    <span>Default Mail App</span>
                  </a>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
