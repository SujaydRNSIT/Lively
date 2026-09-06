import React, { useState, useEffect } from 'react';
import { Mail, User, Building2, Calendar, Video, ArrowRight, X, Bell, CheckCircle2 } from 'lucide-react';

interface EmailCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (email: string, name?: string, company?: string) => Promise<void> | void;
  initialEmail?: string;
  initialName?: string;
  initialCompany?: string;
}

export const EmailCaptureModal: React.FC<EmailCaptureModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialEmail = '',
  initialName = '',
  initialCompany = ''
}) => {
  const [email, setEmail] = useState<string>(initialEmail);
  const [name, setName] = useState<string>(initialName);
  const [company, setCompany] = useState<string>(initialCompany);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      const savedEmail = localStorage.getItem('lively_user_email') || initialEmail || '';
      const savedName = localStorage.getItem('lively_user_name') || initialName || '';
      const savedCompany = localStorage.getItem('lively_user_company') || initialCompany || '';
      setEmail(savedEmail);
      setName(savedName);
      setCompany(savedCompany);
      setError(null);
    }
  }, [isOpen, initialEmail, initialName, initialCompany]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes('@') || !cleanEmail.includes('.')) {
      setError('Please provide a valid email address to receive meeting invites.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      localStorage.setItem('lively_user_email', cleanEmail);
      if (name.trim()) localStorage.setItem('lively_user_name', name.trim());
      if (company.trim()) localStorage.setItem('lively_user_company', company.trim());

      await onSave(cleanEmail, name.trim() || undefined, company.trim() || undefined);
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to save contact information.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => {
    // Mark as prompted for this session so we don't nag repeatedly
    sessionStorage.setItem('lively_prompted_email', 'true');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs transition-opacity duration-300">
      <div 
        className="relative w-full max-w-lg rounded-2xl border hairline bg-[#fdfdfb] dark:bg-[#121623] p-7 sm:p-8 shadow-2xl transition-all transform animate-in fade-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={handleSkip}
          className="absolute top-5 right-5 p-1.5 rounded-lg text-[#8c8a82] hover:text-[#20201e] dark:hover:text-[#f1f0ea] hover:bg-[#eae8e0] dark:hover:bg-[#1e2436] transition cursor-pointer"
          aria-label="Close modal"
        >
          <X size={18} />
        </button>

        {/* Header Pill & Title */}
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] editorial-mono uppercase tracking-[.14em] bg-[#6166cf]/10 text-[#6166cf] font-semibold border border-[#6166cf]/20">
            <Bell size={11} />
            <span>Meeting Notifications & Calendar Sync</span>
          </div>

          <h2 id="modal-title" className="editorial-serif text-2xl sm:text-3xl text-[#20201e] dark:text-[#f1f0ea] leading-tight">
            Stay in the loop with Lively.
          </h2>

          <p className="text-xs sm:text-sm text-[#696862] dark:text-[#9aa0ad] leading-relaxed">
            Enter your email to receive your automated <strong className="text-[#20201e] dark:text-[#f1f0ea]">Google Meet link</strong> and <strong className="text-[#20201e] dark:text-[#f1f0ea]">Google Calendar block</strong> the moment a demo is locked in by voice or UI.
          </p>
        </div>

        {/* Feature Tags */}
        <div className="mt-4 grid grid-cols-2 gap-2.5 p-3 rounded-xl bg-[#f7f6f0] dark:bg-[#181d2c] border hairline text-[11px] text-[#4c4b46] dark:text-[#a09e97]">
          <div className="flex items-center gap-2">
            <Video size={13} className="text-[#6166cf] shrink-0" />
            <span>Instant Google Meet bridge</span>
          </div>
          <div className="flex items-center gap-2">
            <Calendar size={13} className="text-[#6166cf] shrink-0" />
            <span>One-click Calendar block</span>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-5 space-y-3.5">
          <div>
            <label className="block editorial-mono text-[10.5px] uppercase tracking-[.12em] font-semibold text-[#55544e] dark:text-[#a09e97] mb-1.5">
              Email Address <span className="text-[#6166cf]">*</span>
            </label>
            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#8c8a82] dark:text-[#6e7587]" />
              <input
                type="email"
                required
                autoFocus
                placeholder="name@company.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (error) setError(null);
                }}
                className="w-full rounded-xl border hairline bg-white dark:bg-[#101420] pl-10 pr-3.5 py-2.5 text-xs sm:text-sm text-[#20201e] dark:text-[#f1f0ea] placeholder-[#8c8a82] dark:placeholder-[#6e7587] focus:outline-none focus:ring-2 focus:ring-[#6166cf]/40 transition"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block editorial-mono text-[10px] uppercase tracking-[.12em] font-semibold text-[#55544e] dark:text-[#a09e97] mb-1.5">
                Your Name <span className="text-[#8c8a82] dark:text-[#6e7587] font-normal">(Optional)</span>
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8c8a82] dark:text-[#6e7587]" />
                <input
                  type="text"
                  placeholder="Alex Rivera"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-xl border hairline bg-white dark:bg-[#101420] pl-9 pr-3 py-2 text-xs text-[#20201e] dark:text-[#f1f0ea] placeholder-[#8c8a82] dark:placeholder-[#6e7587] focus:outline-none focus:ring-2 focus:ring-[#6166cf]/40 transition"
                />
              </div>
            </div>

            <div>
              <label className="block editorial-mono text-[10px] uppercase tracking-[.12em] font-semibold text-[#55544e] dark:text-[#a09e97] mb-1.5">
                Company <span className="text-[#8c8a82] dark:text-[#6e7587] font-normal">(Optional)</span>
              </label>
              <div className="relative">
                <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#8c8a82] dark:text-[#6e7587]" />
                <input
                  type="text"
                  placeholder="NextGen AI"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full rounded-xl border hairline bg-white dark:bg-[#101420] pl-9 pr-3 py-2 text-xs text-[#20201e] dark:text-[#f1f0ea] placeholder-[#8c8a82] dark:placeholder-[#6e7587] focus:outline-none focus:ring-2 focus:ring-[#6166cf]/40 transition"
                />
              </div>
            </div>
          </div>

          {error && (
            <p className="text-[11px] font-medium text-red-600 dark:text-red-400">
              {error}
            </p>
          )}

          {/* Action Buttons */}
          <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={handleSkip}
              className="px-4 py-2 text-xs font-semibold text-[#696862] hover:text-[#20201e] dark:text-[#9aa0ad] dark:hover:text-[#f1f0ea] transition text-center cursor-pointer order-2 sm:order-1"
            >
              Skip for now
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-[#6166cf] hover:bg-[#5257be] text-white text-xs font-semibold uppercase tracking-[.08em] transition shadow-sm hover:shadow active:scale-95 disabled:opacity-50 cursor-pointer order-1 sm:order-2"
            >
              <span>{isSubmitting ? 'Saving...' : 'Confirm & Enter System'}</span>
              <ArrowRight size={13} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
