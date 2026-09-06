import React from 'react';
import { BookOpen, LayoutDashboard, PlaySquare, BarChart3, Sun, Moon, Mail } from 'lucide-react';
import { AgoraConfig } from '../types';

interface NavbarProps {
  agoraConfig: AgoraConfig | null;
  isConnected: boolean;
  onOpenKnowledge: () => void;
  activeTab: 'cockpit' | 'scenario' | 'analytics';
  setActiveTab: (tab: 'cockpit' | 'scenario' | 'analytics') => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  userEmail?: string;
  onOpenEmailModal?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  isConnected,
  onOpenKnowledge,
  activeTab,
  setActiveTab,
  theme,
  onToggleTheme,
  userEmail,
  onOpenEmailModal,
}) => (
  <header className="sticky top-0 z-40 border-b hairline bg-[#fbfaf7]/95 dark:bg-[#0c0e15]/95 backdrop-blur-md shadow-xs transition-colors duration-200">
    {/* Tier 1: Brand Identity & Session Utilities */}
    <div className="border-b hairline">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-2.5 sm:px-8">
        {/* Left: Official Logo + Slogan */}
        <div className="flex items-center gap-3 sm:gap-4">
          <img
            src={theme === 'dark' ? '/logo-dark.png' : '/logo-light.png'}
            alt="Lively Logo"
            className="h-9 sm:h-10 w-auto object-contain select-none transition-transform hover:scale-[1.02]"
          />
          <div className="hidden sm:block h-4 w-[1px] bg-[#dcdad2] dark:bg-[#202637]" />
          <span className="hidden sm:inline-block editorial-mono text-[9.5px] uppercase tracking-[0.22em] text-[#696862] dark:text-[#9aa0ad] font-semibold">
            LISTEN. ADAPT. REMEMBER. ACT.
          </span>
        </div>

        {/* Right: Live Connection Indicator, Theme Toggle & Playbook Modal Trigger */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* User Email Notification Pill */}
          {onOpenEmailModal && (
            <button
              onClick={onOpenEmailModal}
              title={userEmail ? `Notification email: ${userEmail} (click to update)` : 'Click to set notification email'}
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border hairline bg-[#f4f3ed] dark:bg-[#151926] hover:bg-[#eae8e0] dark:hover:bg-[#1e2436] text-[10px] editorial-mono uppercase tracking-[.12em] text-[#55544e] dark:text-[#9aa0ad] transition cursor-pointer"
            >
              <Mail size={11} className="text-[#6166cf]" />
              <span className="max-w-[150px] truncate">{userEmail || 'Set Email'}</span>
            </button>
          )}

          {/* Standby / On call status badge */}
          <div className="flex items-center gap-2 px-3 py-1 rounded-full border hairline bg-[#f4f3ed] dark:bg-[#151926] text-[10px] editorial-mono uppercase tracking-[.14em] text-[#55544e] dark:text-[#9aa0ad]">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                isConnected ? 'bg-[#10b981] animate-pulse' : 'bg-[#a7a59d] dark:bg-[#525a6f]'
              }`}
            />
            <span>{isConnected ? 'On call' : 'Standby'}</span>
          </div>

          {/* Sun / Moon Theme Toggle */}
          <button
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Switch to Light mode' : 'Switch to Night mode'}
            aria-label={theme === 'dark' ? 'Switch to Light mode' : 'Switch to Night mode'}
            className="inline-flex items-center justify-center h-8 w-8 rounded-lg border hairline bg-white dark:bg-[#151926] hover:bg-[#f5f4ee] dark:hover:bg-[#1e2436] text-[#292927] dark:text-[#e8e6e1] transition shadow-2xs cursor-pointer group"
          >
            {theme === 'dark' ? (
              <Sun size={15} className="text-[#f59e0b] group-hover:rotate-45 transition-transform duration-300" />
            ) : (
              <Moon size={15} className="text-[#6166cf] group-hover:-rotate-12 transition-transform duration-300" />
            )}
          </button>

          {/* Playbook button */}
          <button
            onClick={onOpenKnowledge}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-lg border hairline bg-white dark:bg-[#151926] hover:bg-[#f5f4ee] dark:hover:bg-[#1e2436] text-xs font-medium text-[#292927] dark:text-[#e8e6e1] transition shadow-2xs cursor-pointer"
          >
            <BookOpen size={13} className="text-[#6166cf]" />
            <span>Playbook</span>
          </button>
        </div>
      </div>
    </div>

    {/* Tier 2: Workspace View Navigation Tabs (Center Aligned) */}
    <div className="mx-auto max-w-7xl px-5 sm:px-8 flex justify-center">
      <nav aria-label="workspace views" className="flex items-center justify-center gap-3 sm:gap-8 overflow-x-auto py-0.5 no-scrollbar w-full sm:w-auto">
        <button
          onClick={() => setActiveTab('cockpit')}
          className={`group relative flex shrink-0 items-center gap-2 px-2.5 sm:px-3 py-2.5 text-[11px] font-semibold uppercase tracking-[.12em] transition cursor-pointer ${
            activeTab === 'cockpit'
              ? 'text-[#20201e] dark:text-[#f1f0ea]'
              : 'text-[#77756e] dark:text-[#828896] hover:text-[#20201e] dark:hover:text-[#f1f0ea]'
          }`}
        >
          <LayoutDashboard className={`w-3.5 h-3.5 transition ${activeTab === 'cockpit' ? 'text-[#6166cf]' : 'text-[#8c8a82] dark:text-[#5d6475] group-hover:text-[#20201e] dark:group-hover:text-[#f1f0ea]'}`} />
          <span>Live Sales Cockpit</span>
          {activeTab === 'cockpit' && (
            <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[#6166cf] rounded-full" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('scenario')}
          className={`group relative flex shrink-0 items-center gap-2 px-2.5 sm:px-3 py-2.5 text-[11px] font-semibold uppercase tracking-[.12em] transition cursor-pointer ${
            activeTab === 'scenario'
              ? 'text-[#20201e] dark:text-[#f1f0ea]'
              : 'text-[#77756e] dark:text-[#828896] hover:text-[#20201e] dark:hover:text-[#f1f0ea]'
          }`}
        >
          <PlaySquare className={`w-3.5 h-3.5 transition ${activeTab === 'scenario' ? 'text-[#6166cf]' : 'text-[#8c8a82] dark:text-[#5d6475] group-hover:text-[#20201e] dark:group-hover:text-[#f1f0ea]'}`} />
          <span>Scripted Demo Harness</span>
          <span className="ml-1 px-1.5 py-0.5 rounded text-[8.5px] editorial-mono tracking-normal bg-[#eceae2] dark:bg-[#1e2436] text-[#696862] dark:text-[#9aa0ad] font-medium">
            HACKATHON
          </span>
          {activeTab === 'scenario' && (
            <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[#6166cf] rounded-full" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('analytics')}
          className={`group relative flex shrink-0 items-center gap-2 px-2.5 sm:px-3 py-2.5 text-[11px] font-semibold uppercase tracking-[.12em] transition cursor-pointer ${
            activeTab === 'analytics'
              ? 'text-[#20201e] dark:text-[#f1f0ea]'
              : 'text-[#77756e] dark:text-[#828896] hover:text-[#20201e] dark:hover:text-[#f1f0ea]'
          }`}
        >
          <BarChart3 className={`w-3.5 h-3.5 transition ${activeTab === 'analytics' ? 'text-[#6166cf]' : 'text-[#8c8a82] dark:text-[#5d6475] group-hover:text-[#20201e] dark:group-hover:text-[#f1f0ea]'}`} />
          <span>Telemetry & Latency Observability</span>
          {activeTab === 'analytics' && (
            <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[#6166cf] rounded-full" />
          )}
        </button>
      </nav>
    </div>
  </header>
);
