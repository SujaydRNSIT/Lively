import React, { useState, useEffect } from 'react';
import { X, BookOpen, Search, Shield, Zap, DollarSign, Layers } from 'lucide-react';
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

  useEffect(() => {
    if (isOpen) {
      fetchKnowledgeBase().then(setDocs);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const filteredDocs = docs.filter((d) => {
    const matchesSearch =
      d.title.toLowerCase().includes(search.toLowerCase()) ||
      d.content.toLowerCase().includes(search.toLowerCase()) ||
      d.keywords.some((k) => k.toLowerCase().includes(search.toLowerCase()));
    const matchesCategory = selectedCategory === 'all' || d.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'pricing':
        return <DollarSign className="w-4 h-4 text-emerald-400" />;
      case 'battlecard':
        return <Shield className="w-4 h-4 text-amber-400" />;
      case 'technology':
        return <Zap className="w-4 h-4 text-sky-400" />;
      default:
        return <Layers className="w-4 h-4 text-slate-300" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div className="glass-panel w-full max-w-3xl rounded-2xl border border-surface-border shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-surface-border bg-surface/50">
          <div className="flex items-center space-x-2.5">
            <BookOpen className="w-5 h-5 text-slate-200" />
            <h2 className="text-base font-bold text-white">Lively RAG Knowledge Base & Battlecards</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-hover transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter bar */}
        <div className="p-4 border-b border-surface-border flex flex-col sm:flex-row items-center gap-3 bg-surface/30">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search battlecards, pricing, and Agora architectural specs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-surface/80 border border-surface-border focus:border-white/40 focus:ring-1 focus:ring-white/20 rounded-xl pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center space-x-1.5 w-full sm:w-auto">
            {['all', 'battlecard', 'pricing', 'technology', 'product'].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                  selectedCategory === cat
                    ? 'bg-[#18181b] text-white border border-white/20 shadow-xs'
                    : 'bg-surface text-slate-400 hover:text-slate-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Doc List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {filteredDocs.map((doc) => (
            <div
              key={doc.doc_id}
              className="p-4 rounded-xl bg-surface/60 border border-surface-border hover:border-white/20 transition-all space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  {getCategoryIcon(doc.category)}
                  <h4 className="text-sm font-semibold text-slate-200">{doc.title}</h4>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-mono uppercase bg-white/10 text-slate-200 border border-white/15">
                  {doc.category}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line font-normal">
                {doc.content}
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {doc.keywords.map((kw, i) => (
                  <span
                    key={i}
                    className="text-[10px] px-2 py-0.5 rounded bg-surface border border-surface-border text-slate-400 font-mono"
                  >
                    #{kw}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
