/**
 * Browser Voice Fallback Service using Web Speech API (SpeechRecognition + SpeechSynthesis)
 * Activates seamlessly when the cloud Agora Conversational AI agent is in simulation/mock mode
 * or if WebRTC remote audio is not yet published.
 */
import { streamCustomLlmChat } from './api';

export class BrowserVoiceSession {
  private recognition: any = null;
  private isListening: boolean = false;
  private isSpeaking: boolean = false;
  private channelName: string;
  private onStatusChange: (status: 'idle' | 'listening' | 'thinking' | 'speaking') => void;
  private onTranscriptTurn?: (role: 'buyer' | 'agent', text: string) => void;
  private isStopped: boolean = false;

  constructor(
    channelName: string,
    onStatusChange: (status: 'idle' | 'listening' | 'thinking' | 'speaking') => void,
    onTranscriptTurn?: (role: 'buyer' | 'agent', text: string) => void
  ) {
    this.channelName = channelName;
    this.onStatusChange = onStatusChange;
    this.onTranscriptTurn = onTranscriptTurn;
  }

  public start(): boolean {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn('[BrowserVoice] Web Speech API not supported in this browser.');
      return false;
    }

    this.isStopped = false;
    try {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';

      let accumulated = '';
      let debounceTimer: any = null;

      this.recognition.onresult = (event: any) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            accumulated += event.results[i][0].transcript + ' ';
          } else {
            interim += event.results[i][0].transcript;
          }
        }

        const currentSpeech = (accumulated + interim).trim();
        if (currentSpeech) {
          this.onStatusChange('listening');
          // Interrupt agent speaking if buyer barges in
          if (window.speechSynthesis && window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
          }
        }

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          const textToSend = (accumulated + interim).trim();
          if (textToSend.length >= 2 && !this.isSpeaking) {
            accumulated = '';
            this.onTranscriptTurn?.('buyer', textToSend);
            await this.handleUserSpeech(textToSend);
          }
        }, 800);
      };

      this.recognition.onerror = (event: any) => {
        if (event.error === 'no-speech') return;
        console.warn('[BrowserVoice] Speech recognition event:', event.error);
        if (event.error === 'not-allowed') {
          this.isStopped = true;
        }
      };

      this.recognition.onend = () => {
        if (!this.isStopped && !this.isSpeaking) {
          try {
            this.recognition.start();
          } catch (e) {
            // Already started or busy
          }
        }
      };

      this.recognition.start();
      this.isListening = true;
      console.log('[BrowserVoice] Speech recognition active.');
      return true;
    } catch (err) {
      console.error('[BrowserVoice] Failed to initialize SpeechRecognition:', err);
      return false;
    }
  }

  private async handleUserSpeech(text: string) {
    this.isSpeaking = true;
    this.onStatusChange('thinking');

    try {
      this.recognition?.stop();
    } catch (e) {}

    try {
      let agentReply = '';
      await streamCustomLlmChat(
        this.channelName,
        [{ role: 'user', content: text }],
        (chunk) => {
          agentReply += chunk;
        }
      );

      if (agentReply.trim()) {
        this.onTranscriptTurn?.('agent', agentReply);
        this.speak(agentReply);
      } else {
        this.isSpeaking = false;
        this.onStatusChange('idle');
        this.restartListening();
      }
    } catch (err) {
      console.error('[BrowserVoice] Failed to get LLM response:', err);
      this.isSpeaking = false;
      this.onStatusChange('idle');
      this.restartListening();
    }
  }

  public speak(text: string) {
    if (!window.speechSynthesis) {
      this.isSpeaking = false;
      this.onStatusChange('idle');
      this.restartListening();
      return;
    }

    this.isSpeaking = true;
    this.onStatusChange('speaking');
    window.speechSynthesis.cancel();

    // Strip markdown formatting symbols for spoken English
    const cleanText = text
      .replace(/[*_#`]/g, '')
      .replace(/<[^>]*>/g, '')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;
    utterance.lang = 'en-US';

    const voices = window.speechSynthesis.getVoices();
    const naturalVoice =
      voices.find(
        (v) =>
          v.lang.startsWith('en') &&
          (v.name.includes('Natural') ||
            v.name.includes('Google') ||
            v.name.includes('Jenny') ||
            v.name.includes('Samantha') ||
            v.name.includes('Microsoft'))
      ) || voices.find((v) => v.lang.startsWith('en'));

    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    utterance.onend = () => {
      this.isSpeaking = false;
      this.onStatusChange('idle');
      this.restartListening();
    };

    utterance.onerror = () => {
      this.isSpeaking = false;
      this.onStatusChange('idle');
      this.restartListening();
    };

    window.speechSynthesis.speak(utterance);
  }

  private restartListening() {
    if (!this.isStopped) {
      setTimeout(() => {
        try {
          this.recognition?.start();
        } catch (e) {}
      }, 200);
    }
  }

  public stop() {
    this.isStopped = true;
    this.isListening = false;
    this.isSpeaking = false;
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {}
      this.recognition = null;
    }
  }
}
