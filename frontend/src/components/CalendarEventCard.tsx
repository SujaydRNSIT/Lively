import React, { useState } from 'react';
import { Calendar, Clock, Video, CheckCircle, ExternalLink, UserCheck, Copy, Check, MailCheck, Send, RefreshCw, Mail } from 'lucide-react';
import { sendMeetingInvite } from '../services/api';
import { ScheduledDemo } from '../types';

interface CalendarEventCardProps {
  channelName: string;
  demoData: ScheduledDemo;
}

export const INVITE_STATUS_LABELS: Record<string, string> = {
  queued: 'Sending invite…',
  sending: 'Sending invite…',
  delivered: 'Invite delivered',
  preview_only: 'Invite saved locally (email not configured)',
  pending_email: 'Waiting for the buyer’s email',
  rate_limited: 'Invite limit reached',
};

export const CalendarEventCard: React.FC<CalendarEventCardProps> = ({ channelName, demoData }) => {
  const storedEmail = (() => {
    try {
      return localStorage.getItem('lively_user_email') || '';
    } catch {
      return '';
    }
  })();
  const [recipientEmail, setRecipientEmail] = useState<string>(demoData.email || storedEmail);
  const [copied, setCopied] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [sendStatus, setSendStatus] = useState<{ success: boolean; message: string } | null>(null);

  const meetingLink = demoData.meeting_link;
  const topic = demoData.topic || 'Lively Real-Time Voice AI Sales Deep-Dive';
  const host = demoData.host || 'Senior Solutions Architect';
  const inviteLabel = INVITE_STATUS_LABELS[demoData.invite_status || ''] || '';

  const gmailComposeUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(recipientEmail || '')}&su=${encodeURIComponent(`Lively AI demo: ${demoData.time}`)}&body=${encodeURIComponent(`Your product walkthrough is scheduled for ${demoData.time}.\n\nVideo room: ${meetingLink}\nAdd to Google Calendar: ${demoData.google_calendar_link || ''}\n\nHost: ${host}\nTopic: ${topic}`)}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(meetingLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSendInvite = async () => {
    let email = recipientEmail.trim();
    if (!email.includes('@')) {
      const prompted = window.prompt('Enter the email address that should receive the calendar invite:', storedEmail);
      if (!prompted || !prompted.includes('@')) return;
      email = prompted.trim();
      setRecipientEmail(email);
      try {
        localStorage.setItem('lively_user_email', email);
      } catch {
        // ignore storage error
      }
    }
    setIsSending(true);
    setSendStatus(null);
    try {
      const res = await sendMeetingInvite(channelName, email);
      setSendStatus({ success: true, message: res.message });
    } catch (err: any) {
      setSendStatus({ success: false, message: err.message || 'Could not send the invite. Use Add to Calendar instead.' });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="rounded-2xl border hairline bg-[#fdfdfb] dark:bg-[#121623] p-5 shadow-xs transition-colors">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b hairline">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-black/5 dark:bg-white/10 text-[#20201e] dark:text-[#f1f0ea] border hairline">
            <Calendar className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="editorial-mono text-[9.5px] uppercase tracking-[0.16em] font-semibold text-[#20201e] dark:text-[#f1f0ea]">Confirmed Event</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-[#10b981]/10 px-2 py-0.5 text-[9px] font-semibold text-[#10b981] border border-[#10b981]/20">
                <CheckCircle className="h-2.5 w-2.5" />
                Slot checked against the calendar
              </span>
            </div>
            <h3 className="text-sm font-semibold text-[#20201e] dark:text-[#f1f0ea] mt-0.5">{topic}</h3>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          {demoData.google_calendar_link && (
            <a
              href={demoData.google_calendar_link}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-neutral-300 dark:border-neutral-700 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800/80 dark:hover:bg-neutral-800 text-neutral-900 dark:text-neutral-100 text-xs font-semibold shadow-xs transition cursor-pointer"
            >
              <Calendar className="h-3.5 w-3.5" />
              <span>Add to Calendar</span>
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          )}
          <a
            href={meetingLink}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#141416] hover:bg-[#222227] text-white dark:bg-[#18191e] dark:hover:bg-[#252730] dark:text-[#f4f3ef] border border-black/20 dark:border-white/15 text-xs font-semibold shadow-xs transition-transform active:scale-95 cursor-pointer"
          >
            <Video className="h-3.5 w-3.5" />
            <span>Join video room</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 py-3 text-xs">
        <div className="flex items-center gap-2 text-[#4c4b46] dark:text-[#9aa0ad]">
          <Clock className="h-4 w-4 text-[#20201e] dark:text-[#e8e6e1] shrink-0" />
          <span><strong>Time:</strong> {demoData.time}</span>
        </div>
        <div className="flex items-center gap-2 text-[#4c4b46] dark:text-[#9aa0ad]">
          <UserCheck className="h-4 w-4 text-[#20201e] dark:text-[#e8e6e1] shrink-0" />
          <span><strong>Host:</strong> {host}</span>
        </div>
        <div className="flex items-center gap-2 text-[#4c4b46] dark:text-[#9aa0ad]">
          <MailCheck className="h-4 w-4 text-[#10b981] shrink-0" />
          <span><strong>Invite:</strong> {inviteLabel || '—'}</span>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t hairline bg-[#f7f6f0] dark:bg-[#181d2c] p-3.5 rounded-xl">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          <p className="text-xs font-medium text-[#20201e] dark:text-[#f1f0ea] truncate">
            Recipient: <span className="font-semibold text-[#20201e] dark:text-[#f1f0ea] underline decoration-neutral-400 dark:decoration-neutral-600">{demoData.email || recipientEmail || 'No email yet — the agent will ask for one'}</span>
          </p>
          <div className="flex items-center gap-2 shrink-0 flex-wrap sm:flex-nowrap">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#4c4b46] dark:text-[#d1d5db] hover:bg-[#f3f2eb] dark:hover:bg-[#1e2436] transition cursor-pointer"
            >
              {copied ? <Check className="h-3 w-3 text-[#10b981]" /> : <Copy className="h-3 w-3 text-[#20201e] dark:text-[#e8e6e1]" />}
              <span>{copied ? 'Copied' : 'Copy room link'}</span>
            </button>
            <button
              onClick={handleSendInvite}
              disabled={isSending}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#20201e] dark:text-[#e8e6e1] hover:bg-[#f3f2eb] dark:hover:bg-[#1e2436] transition cursor-pointer disabled:opacity-50"
            >
              {isSending ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />}
              <span>{isSending ? 'Sending...' : 'Send invite'}</span>
            </button>
            <a
              href={gmailComposeUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border hairline bg-white dark:bg-[#101420] text-xs font-medium text-[#ea4335] hover:bg-[#ea4335]/10 transition cursor-pointer"
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
