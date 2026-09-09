import AgoraRTC, {
  IAgoraRTCClient,
  IMicrophoneAudioTrack,
  ILocalAudioTrack,
  IRemoteAudioTrack,
} from 'agora-rtc-sdk-ng';

export class AgoraVoiceManager {
  private client: IAgoraRTCClient | null = null;
  private localAudioTrack: IMicrophoneAudioTrack | ILocalAudioTrack | null = null;
  private remoteAudioTrack: IRemoteAudioTrack | null = null;
  private onVolumeChange?: (localLevel: number, remoteLevel: number) => void;
  private onAgentConnected?: () => void;
  private onAgentDisconnected?: () => void;
  private isConnected: boolean = false;
  private currentChannel: string = '';

  constructor(callbacks?: {
    onVolumeChange?: (localLevel: number, remoteLevel: number) => void;
    onAgentConnected?: () => void;
    onAgentDisconnected?: () => void;
  }) {
    if (callbacks) {
      this.onVolumeChange = callbacks.onVolumeChange;
      this.onAgentConnected = callbacks.onAgentConnected;
      this.onAgentDisconnected = callbacks.onAgentDisconnected;
    }
  }

  public static async checkMicrophone(): Promise<{ available: boolean; error?: string }> {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return { available: false, error: 'WebRTC audio is not supported in this browser environment.' };
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      return { available: true };
    } catch (err: any) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        return { available: false, error: 'Microphone permission denied. Please click the camera/lock icon in your address bar and allow microphone access.' };
      }
      if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        return { available: false, error: 'No microphone found on your system. Please plug in a headset or microphone.' };
      }
      return { available: false, error: err.message || 'Microphone access failed.' };
    }
  }

  public async joinChannel(
    appId: string,
    channelName: string,
    token: string,
    uid: number = 1001
  ): Promise<boolean> {
    try {
      this.currentChannel = channelName;
      this.client = AgoraRTC.createClient({ mode: 'rtc', codec: 'vp8' });

      // Listen for remote agent audio publishing
      this.client.on('user-published', async (user, mediaType) => {
        if (mediaType === 'audio') {
          try {
            const track = await this.client!.subscribe(user, mediaType);
            this.remoteAudioTrack = track;
            track.play();
            if (this.onAgentConnected) this.onAgentConnected();
          } catch (subErr) {
            console.warn('[AgoraRTC] Error subscribing to remote audio track:', subErr);
          }
        }
      });

      this.client.on('user-unpublished', (user, mediaType) => {
        if (mediaType === 'audio' && this.onAgentDisconnected) {
          this.onAgentDisconnected();
        }
      });

      // Enable audio volume indicators (for wave visualizers)
      try {
        AgoraRTC.enableLogUpload();
      } catch (e) {}

      this.client.enableAudioVolumeIndicator();
      this.client.on('volume-indicator', (volumes) => {
        let localVol = 0;
        let remoteVol = 0;
        volumes.forEach((vol) => {
          if (vol.uid === uid || vol.uid === 0) {
            localVol = vol.level;
          } else {
            remoteVol = Math.max(remoteVol, vol.level);
          }
        });
        if (this.onVolumeChange) {
          this.onVolumeChange(localVol, remoteVol);
        }
      });

      console.log(`[AgoraRTC] Joining channel "${channelName}" with appId: ${appId}, uid: ${uid}, token length: ${token?.length || 0}`);
      // Join channel
      await this.client.join(appId, channelName, token || null, uid);
      console.log('[AgoraRTC] Successfully joined channel. Creating microphone audio track...');

      // 5-Tier Resilient Microphone Track Acquisition
      let acquiredTrack: IMicrophoneAudioTrack | ILocalAudioTrack | null = null;

      // Tier 1: Agora recommended standard voice encoder (48kHz mono, 32kbps) with AEC, ANS, AGC
      try {
        acquiredTrack = await AgoraRTC.createMicrophoneAudioTrack({
          encoderConfig: 'music_standard',
          AEC: true,
          ANS: true,
          AGC: true,
        });
        console.log('[AgoraRTC] Tier 1 mic created successfully (music_standard + AEC/ANS/AGC).');
      } catch (e1) {
        console.warn('[AgoraRTC] Tier 1 mic creation failed:', e1);
      }

      // Tier 2: speech_standard (32kHz) fallback
      if (!acquiredTrack) {
        try {
          acquiredTrack = await AgoraRTC.createMicrophoneAudioTrack({
            encoderConfig: 'speech_standard',
            AEC: true,
            ANS: true,
            AGC: true,
          });
          console.log('[AgoraRTC] Tier 2 mic created successfully (speech_standard).');
        } catch (e2) {
          console.warn('[AgoraRTC] Tier 2 mic creation failed:', e2);
        }
      }

      // Tier 3: Default system audio constraints without custom encoderConfig
      if (!acquiredTrack) {
        try {
          acquiredTrack = await AgoraRTC.createMicrophoneAudioTrack({
            AEC: true,
            ANS: true,
          });
          console.log('[AgoraRTC] Tier 3 mic created successfully (system constraints).');
        } catch (e3) {
          console.warn('[AgoraRTC] Tier 3 mic creation failed:', e3);
        }
      }

      // Tier 4: Zero constraints vanilla Agora mic track
      if (!acquiredTrack) {
        try {
          acquiredTrack = await AgoraRTC.createMicrophoneAudioTrack();
          console.log('[AgoraRTC] Tier 4 mic created successfully (vanilla Agora track).');
        } catch (e4) {
          console.warn('[AgoraRTC] Tier 4 mic creation failed:', e4);
        }
      }

      // Tier 5: Direct browser navigator.mediaDevices.getUserMedia wrapped in createCustomAudioTrack
      if (!acquiredTrack && typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        try {
          const mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });
          const rawTrack = mediaStream.getAudioTracks()[0];
          if (rawTrack) {
            acquiredTrack = AgoraRTC.createCustomAudioTrack({ mediaStreamTrack: rawTrack });
            console.log('[AgoraRTC] Tier 5 mic created successfully (raw MediaStreamTrack).');
          }
        } catch (e5) {
          console.error('[AgoraRTC] Tier 5 mic creation failed:', e5);
        }
      }

      if (!acquiredTrack) {
        throw new Error('Could not access any microphone. Please check browser permissions and verify your microphone is plugged in.');
      }

      this.localAudioTrack = acquiredTrack;
      try {
        this.localAudioTrack.setVolume(100);
      } catch (e) {}

      console.log('[AgoraRTC] Microphone audio track ready. Publishing track...');
      await this.client.publish([this.localAudioTrack]);
      console.log('[AgoraRTC] Microphone track published successfully!');
      this.isConnected = true;
      return true;
    } catch (error) {
      console.error('[AgoraRTC] Failed to join channel or acquire microphone:', error);
      throw error;
    }
  }

  public async leaveChannel(): Promise<void> {
    try {
      if (this.localAudioTrack) {
        this.localAudioTrack.stop();
        this.localAudioTrack.close();
        this.localAudioTrack = null;
      }
      if (this.remoteAudioTrack) {
        this.remoteAudioTrack.stop();
        this.remoteAudioTrack = null;
      }
      if (this.client) {
        await this.client.leave();
        this.client = null;
      }
      this.isConnected = false;
    } catch (e) {
      console.error('Error leaving channel:', e);
    }
  }

  public setMute(muted: boolean): boolean {
    if (this.localAudioTrack) {
      this.localAudioTrack.setEnabled(!muted);
      return !muted;
    }
    return false;
  }

  public getIsConnected(): boolean {
    return this.isConnected;
  }
}

