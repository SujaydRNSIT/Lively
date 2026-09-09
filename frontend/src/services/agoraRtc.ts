import AgoraRTC, {
  IAgoraRTCClient,
  IMicrophoneAudioTrack,
  IRemoteAudioTrack,
} from 'agora-rtc-sdk-ng';

export class AgoraVoiceManager {
  private client: IAgoraRTCClient | null = null;
  private localAudioTrack: IMicrophoneAudioTrack | null = null;
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
          const track = await this.client!.subscribe(user, mediaType);
          this.remoteAudioTrack = track;
          track.play();
          if (this.onAgentConnected) this.onAgentConnected();
        }
      });

      this.client.on('user-unpublished', (user, mediaType) => {
        if (mediaType === 'audio' && this.onAgentDisconnected) {
          this.onAgentDisconnected();
        }
      });

      // Enable audio volume indicators (for wave visualizers)
      AgoraRTC.enableLogUpload();
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

      // Create and publish local microphone with resilient fallback
      try {
        this.localAudioTrack = await AgoraRTC.createMicrophoneAudioTrack({
          encoderConfig: 'speech_standard',
          AEC: true,
          ANS: true,
          AGC: true,
        });
      } catch (trackError) {
        console.warn('[AgoraRTC] Standard encoderConfig failed, falling back to default mic constraints:', trackError);
        this.localAudioTrack = await AgoraRTC.createMicrophoneAudioTrack({
          AEC: true,
          ANS: true,
          AGC: true,
        });
      }

      console.log('[AgoraRTC] Microphone audio track created. Publishing track...');
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
