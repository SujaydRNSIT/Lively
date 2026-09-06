import React, { useState } from 'react';
import { Calendar, Clock, Video, CheckCircle, ExternalLink, UserCheck, ShieldCheck, Copy, Check, MailCheck } from 'lucide-react';

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
  demoData
}) => {
  const meetingTime = demoData?.time || "Tomorrow at 2:00 PM EST";
  const userStoredEmail = typeof window !== 'undefined' ? localStorage.getItem('lively_user_email') || '' : '';
  const recipientEmail = (demoData?.email && demoData.email !== "prospect@example.com" && demoData.email !== "alex.rivera@nextgen.ai")
    ? demoData.email
    : userStoredEmail || demoData?.email || "your email";

  const meetingLink = demoData?.meeting_link || "https://meet.google.com/new";
  const topic = demoData?.topic || "Lively Real-Time Voice AI Sales Deep-Dive";
  const host = demoData?.host || "Senior Solutions Architect";

  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(meetingLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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

      {/* Final Meet Link & Automated Dispatch Notice */}
      <div className="mt-3 pt-3 border-t hairline bg-[#f7f6f0] dark:bg-[#181d2c] p-3.5 rounded-xl">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-7 w-7 rounded-lg bg-[#10b981]/15 text-[#10b981] flex items-center justify-center shrink-0">
              <MailCheck className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-[#20201e] dark:text-[#f1f0ea] truncate">
                Google Meet bridge & calendar invite dispatched to <span className="font-semibold text-[#6166cf]">{recipientEmail}</span>
              </p>
              <p className="text-[11px] text-[#77756e] dark:text-[#9aa0ad] truncate">
                Lively automatically booked this reservation on the calendar
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#4c4b46] dark:text-[#d1d5db] hover:bg-[#f3f2eb] dark:hover:bg-[#1e2436] transition cursor-pointer"
            >
              {copied ? <Check className="h-3 w-3 text-[#10b981]" /> : <Copy className="h-3 w-3 text-[#6166cf]" />}
              <span>{copied ? 'Copied!' : 'Copy Meet Link'}</span>
            </button>

            <a
              href={meetingLink}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#20201e] dark:bg-[#f1f0ea] text-white dark:text-[#121623] text-xs font-semibold hover:opacity-90 transition cursor-pointer"
            >
              <Video className="h-3 w-3" />
              <span>Open Meet</span>
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
