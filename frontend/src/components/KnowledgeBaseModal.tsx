import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  X,
  BookOpen,
  Search,
  Shield,
  Zap,
  DollarSign,
  Layers,
  Sparkles,
  Tag,
  Copy,
  Check,
  Database,
  SearchX,
} from 'lucide-react';
import { RAGDocument } from '../types';
import { fetchKnowledgeBase } from '../services/api';

interface KnowledgeBaseModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const KnowledgeBaseModal: React.FC<KnowledgeBaseModalProps> = ({ isOpen, onClose }) => {
  const [docs, setDocs] = useState<RAGDocument[]>([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      fetchKnowledgeBase().then(setDocs).catch((err) => {
        console.warn('Failed to load knowledge base:', err);
      });
      // Auto focus search after opening
      setTimeout(() => searchInputRef.current?.focus(), 100);
    } else {
      setSearch('');
      setSelectedCategory('all');
    }
  }, [isOpen]);

  // Keyboard shortcut listener: ESC to close, / to search
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === '/' && document.activeElement !== searchInputRef.current) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const categories = useMemo(() => {
    return [
      { id: 'all', label: 'All', icon: Layers },
      { id: 'battlecard', label: 'Battlecards', icon: Shield },
      { id: 'pricing', label: 'Pricing', icon: DollarSign },
      { id: 'technology', label: 'Technology', icon: Zap },
      { id: 'product', label: 'Product', icon: Sparkles },
    ];
  }, []);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: docs.length };
    for (const d of docs) {
      const cat = (d.category || '').toLowerCase();
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return counts;
  }, [docs]);

  const filteredDocs = useMemo(() => {
    const q = search.trim().toLowerCase();
    return docs.filter((d) => {
      const matchesCategory = selectedCategory === 'all' || (d.category || '').toLowerCase() === selectedCategory;
      if (!matchesCategory) return false;
      if (!q) return true;
      return (
        d.title.toLowerCase().includes(q) ||
        d.content.toLowerCase().includes(q) ||
        (d.keywords && d.keywords.some((k) => k.toLowerCase().includes(q)))
      );
    });
  }, [docs, search, selectedCategory]);

  const handleCopy = (doc: RAGDocument) => {
    const text = `${doc.title}\n\n${doc.content}`;
    navigator.clipboard?.writeText(text);
    setCopiedId(doc.doc_id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  if (!isOpen) return null;

  const getCategoryConfig = (category: string) => {
    const cat = (category || '').toLowerCase();
    switch (cat) {
      case 'pricing':
        return {
          icon: DollarSign,
          iconColor: 'text-emerald-600 dark:text-emerald-400',
          badgeBg: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/25',
          label: 'PRICING',
        };
      case 'battlecard':
        return {
          icon: Shield,
          iconColor: 'text-amber-600 dark:text-amber-400',
          badgeBg: 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/25',
          label: 'BATTLECARD',
        };
      case 'technology':
        return {
          icon: Zap,
          iconColor: 'text-sky-600 dark:text-sky-400',
          badgeBg: 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/25',
          label: 'TECHNOLOGY',
        };
      case 'product':
        return {
          icon: Sparkles,
          iconColor: 'text-purple-600 dark:text-purple-400',
          badgeBg: 'bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/25',
          label: 'PRODUCT',
        };
      default:
        return {
          icon: Layers,
          iconColor: 'text-[#696862] dark:text-[#9aa0ad]',
          badgeBg: 'bg-[#f4f3ed] dark:bg-[#1a1e2e] text-[#55544e] dark:text-[#9aa0ad] border-neutral-300 dark:border-neutral-700',
          label: category.toUpperCase(),
        };
    }
  };

  // Helper to format content blocks (bullet points vs paragraphs)
  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n').map((l) => l.trim()).filter(Boolean);
    return (
      <div className="space-y-2">
        {lines.map((line, idx) => {
          if (line.startsWith('- ') || line.startsWith('* ')) {
            const bulletText = line.replace(/^[-*]\s+/, '');
            // Highlight bold terms like **Tier Name:** or Starting words before colon
            const colonIdx = bulletText.indexOf(':');
            if (colonIdx > 0 && colonIdx < 35) {
              const prefix = bulletText.slice(0, colonIdx + 1);
              const rest = bulletText.slice(colonIdx + 1);
              return (
                <div key={idx} className="flex items-start gap-2.5 py-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#20201e]/60 dark:bg-white/60 mt-1.5 shrink-0" />
                  <p className="text-xs sm:text-[13px] leading-relaxed text-[#4c4b46] dark:text-[#a09e97]">
                    <strong className="font-semibold text-[#20201e] dark:text-[#f1f0ea]">{prefix}</strong>
                    {rest}
                  </p>
                </div>
              );
            }
            return (
              <div key={idx} className="flex items-start gap-2.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#20201e]/60 dark:bg-white/60 mt-1.5 shrink-0" />
                <p className="text-xs sm:text-[13px] leading-relaxed text-[#4c4b46] dark:text-[#a09e97]">
                  {bulletText}
                </p>
              </div>
            );
          }

          if (line.endsWith(':')) {
            return (
              <h5
                key={idx}
                className="editorial-mono text-[11px] uppercase tracking-[.14em] font-semibold text-[#20201e] dark:text-[#e8e6e1] pt-1.5"
              >
                {line}
              </h5>
            );
          }

          return (
            <p key={idx} className="text-xs sm:text-[13px] leading-relaxed text-[#4c4b46] dark:text-[#a09e97]">
              {line}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/60 dark:bg-black/80 backdrop-blur-md transition-opacity">
      <div className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl sm:rounded-3xl border hairline bg-[#fbfaf7] dark:bg-[#0e111a] shadow-2xl overflow-hidden transition-all duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-5 sm:px-7 py-4 sm:py-5 border-b hairline bg-white/70 dark:bg-[#121622]/70 backdrop-blur-md">
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="p-2.5 rounded-xl border hairline bg-[#f4f3ed] dark:bg-[#181d2c] text-[#20201e] dark:text-[#f1f0ea] shadow-xs">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="editorial-serif text-xl sm:text-2xl text-[#20201e] dark:text-[#f1f0ea]">
                  Lively RAG Knowledge & Battlecards
                </h2>
                <span className="editorial-mono text-[9px] uppercase tracking-[.15em] px-2 py-0.5 rounded-full border hairline bg-[#eceae2] dark:bg-[#1a1e2e] text-[#696862] dark:text-[#9aa0ad] hidden md:inline-block">
                  {filteredDocs.length} {filteredDocs.length === 1 ? 'doc' : 'docs'}
                </span>
              </div>
              <p className="editorial-mono text-[10.5px] uppercase tracking-[.14em] text-[#696862] dark:text-[#9aa0ad] mt-0.5">
                Ground-truth enterprise sales playbooks, pricing & competitive intelligence
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border hairline bg-white dark:bg-[#181d2c] hover:bg-[#eceae2] dark:hover:bg-[#202637] text-[#696862] dark:text-[#9aa0ad] hover:text-[#20201e] dark:hover:text-[#f1f0ea] transition cursor-pointer"
            title="Close modal (Esc)"
          >
            <span className="editorial-mono text-[10px] opacity-60 hidden sm:inline">ESC</span>
            <X size={15} />
          </button>
        </div>

        {/* Search and Category Filter Toolbar */}
        <div className="px-5 sm:px-7 py-3.5 border-b hairline bg-[#f4f3ed]/60 dark:bg-[#121622]/40 flex flex-col sm:flex-row items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#8c8a82] dark:text-[#646c82]" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search battlecards, pricing, and Agora architectural specs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-white dark:bg-[#181d2c] border hairline focus:border-[#20201e] dark:focus:border-white/40 rounded-xl pl-10 pr-9 py-2 text-xs sm:text-sm text-[#20201e] dark:text-[#f1f0ea] placeholder-[#8c8a82] dark:placeholder-[#646c82] shadow-2xs focus:outline-none transition"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded-md text-[#8c8a82] hover:text-[#20201e] dark:hover:text-white"
                title="Clear search"
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
            {categories.map((cat) => {
              const count = categoryCounts[cat.id] ?? 0;
              const isSelected = selectedCategory === cat.id;
              const Icon = cat.icon;
              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition cursor-pointer shrink-0 ${
                    isSelected
                      ? 'bg-[#20201e] text-white dark:bg-white dark:text-[#0c0e15] shadow-xs'
                      : 'bg-white/80 dark:bg-[#181d2c]/80 border hairline text-[#55544e] dark:text-[#9aa0ad] hover:bg-[#eceae2] dark:hover:bg-[#202637] hover:text-[#20201e] dark:hover:text-[#f1f0ea]'
                  }`}
                >
                  <Icon size={13} className={isSelected ? 'text-inherit' : 'opacity-70'} />
                  <span>{cat.label}</span>
                  <span
                    className={`editorial-mono text-[9.5px] px-1.5 py-0.2 rounded-full ${
                      isSelected
                        ? 'bg-white/20 text-white dark:bg-black/20 dark:text-[#0c0e15]'
                        : 'bg-[#eceae2] dark:bg-[#202637] text-[#696862] dark:text-[#9aa0ad]'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Document List */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-7 space-y-4">
          {filteredDocs.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <div className="inline-flex p-3 rounded-2xl border hairline bg-[#f4f3ed] dark:bg-[#181d2c] text-[#8c8a82]">
                <SearchX className="w-8 h-8" />
              </div>
              <p className="editorial-serif text-2xl italic text-[#4c4b46] dark:text-[#9aa0ad]">
                No knowledge records found
              </p>
              <p className="text-xs text-[#77756e] dark:text-[#646c82] max-w-sm mx-auto">
                No battlecards match your search &quot;{search}&quot;. Try selecting another category or clear the search.
              </p>
              {(search || selectedCategory !== 'all') && (
                <button
                  onClick={() => {
                    setSearch('');
                    setSelectedCategory('all');
                  }}
                  className="editorial-mono text-xs uppercase tracking-[.12em] px-4 py-1.5 rounded-lg border hairline bg-white dark:bg-[#181d2c] text-[#20201e] dark:text-[#f1f0ea] hover:bg-[#eceae2] dark:hover:bg-[#202637] transition cursor-pointer"
                >
                  Reset Filters
                </button>
              )}
            </div>
          ) : (
            filteredDocs.map((doc) => {
              const cfg = getCategoryConfig(doc.category);
              const Icon = cfg.icon;
              const isCopied = copiedId === doc.doc_id;

              return (
                <article
                  key={doc.doc_id}
                  className="rounded-2xl border hairline bg-white dark:bg-[#141824] p-5 sm:p-6 hover:border-[#20201e]/30 dark:hover:border-white/20 hover:shadow-md transition-all duration-200 group flex flex-col gap-3.5"
                >
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div
                        className={`p-2 rounded-xl shrink-0 mt-0.5 border ${cfg.badgeBg}`}
                      >
                        <Icon size={16} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`editorial-mono text-[9px] uppercase tracking-[.16em] px-2 py-0.5 rounded-md font-semibold border ${cfg.badgeBg}`}
                          >
                            {cfg.label}
                          </span>
                        </div>
                        <h3 className="editorial-serif text-lg sm:text-xl font-semibold text-[#20201e] dark:text-[#f1f0ea] mt-1 group-hover:text-black dark:group-hover:text-white transition">
                          {doc.title}
                        </h3>
                      </div>
                    </div>

                    <button
                      onClick={() => handleCopy(doc)}
                      title="Copy knowledge text"
                      className="p-2 rounded-xl border hairline bg-[#fbfaf7] dark:bg-[#181d2c] hover:bg-[#eceae2] dark:hover:bg-[#202637] text-[#696862] dark:text-[#9aa0ad] hover:text-[#20201e] dark:hover:text-[#f1f0ea] transition cursor-pointer shrink-0"
                    >
                      {isCopied ? (
                        <Check size={14} className="text-emerald-500" />
                      ) : (
                        <Copy size={14} />
                      )}
                    </button>
                  </div>

                  {/* Card Body with formatted lines */}
                  <div className="pt-1">{renderFormattedContent(doc.content)}</div>

                  {/* Keywords Tag Bar */}
                  {doc.keywords && doc.keywords.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-3 border-t hairline">
                      <span className="editorial-mono text-[9.5px] uppercase tracking-[.14em] text-[#8c8a82] dark:text-[#646c82] flex items-center gap-1 mr-1">
                        <Tag size={10} />
                        Topics:
                      </span>
                      {doc.keywords.map((kw, i) => (
                        <button
                          key={i}
                          onClick={() => setSearch(kw)}
                          title={`Search for "${kw}"`}
                          className="editorial-mono text-[10px] px-2 py-0.5 rounded-md border hairline bg-[#f7f6f2] dark:bg-[#181d2c] text-[#55544e] dark:text-[#9aa0ad] hover:bg-[#eceae2] dark:hover:bg-[#252b40] hover:text-[#20201e] dark:hover:text-[#f1f0ea] transition cursor-pointer"
                        >
                          #{kw}
                        </button>
                      ))}
                    </div>
                  )}
                </article>
              );
            })
          )}
        </div>

        {/* Footer Status Bar */}
        <div className="px-5 sm:px-7 py-3 border-t hairline bg-[#f4f3ed]/60 dark:bg-[#121622]/60 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Database size={13} className="text-emerald-500" />
            <span className="editorial-mono text-[10px] text-[#696862] dark:text-[#9aa0ad]">
              Pinecone Vector Index <code className="font-semibold text-[#20201e] dark:text-[#f1f0ea]">lively-rag</code> &bull; Cosine Similarity Retrieval
            </span>
          </div>
          <span className="editorial-mono text-[10px] text-[#8c8a82] dark:text-[#646c82] hidden sm:inline">
            Use <kbd className="px-1.5 py-0.5 rounded border hairline bg-white dark:bg-[#181d2c] text-[9px] font-mono shadow-2xs">ESC</kbd> to exit &bull; <kbd className="px-1.5 py-0.5 rounded border hairline bg-white dark:bg-[#181d2c] text-[9px] font-mono shadow-2xs">/</kbd> to search
          </span>
        </div>
      </div>
    </div>
  );
};
