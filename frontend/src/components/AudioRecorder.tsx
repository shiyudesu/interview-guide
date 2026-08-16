import { useRef, useState, useEffect } from 'react';
// @ts-ignore - vad is loaded via script tag
import { Mic, MicOff } from 'lucide-react';

// Declare global vad object (loaded via script tag in index.html)
declare global {
  interface Window {
    vad: {
      MicVAD: {
        new: (config: any) => Promise<{
          start: () => Promise<void>;
          pause: () => void;
          destroy: () => void;
        }>;
      };
    };
  }
}

interface AudioRecorderProps {
  isRecording: boolean;
  disabled?: boolean;
  onRecordingChange: (isRecording: boolean) => void;
  onAudioData: (audioData: string) => void;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

export default function AudioRecorder({
  isRecording,
  disabled = false,
  onRecordingChange,
  onAudioData,
  onSpeechStart,
  onSpeechEnd,
}: AudioRecorderProps) {
  const [volume, setVolume] = useState(0);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const vadRef = useRef<any>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null);
  // Mount flag to prevent operations after unmount
  const mountedRef = useRef(true);
  // Recording lifecycle flag for async callbacks while the component remains mounted.
  const recordingActiveRef = useRef(false);
  // Flag to track if we're in the middle of starting
  const startingRef = useRef(false);

  const TARGET_SAMPLE_RATE = 16000;

  const cleanupRecordingResources = (updateVolume = true) => {
    recordingActiveRef.current = false;

    if (vadRef.current) {
      try {
        vadRef.current.pause();
        vadRef.current.destroy?.();
      } catch (e) {
        // Ignore cleanup errors
      }
      vadRef.current = null;
    }

    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (workletNodeRef.current) {
      try {
        workletNodeRef.current.port.onmessage = null;
        workletNodeRef.current.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
      workletNodeRef.current = null;
    }

    if (gainNodeRef.current) {
      try {
        gainNodeRef.current.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
      gainNodeRef.current = null;
    }

    if (analyserRef.current) {
      try {
        analyserRef.current.disconnect();
      } catch (e) {
        // Ignore disconnect errors
      }
      analyserRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch (e) {
        // Ignore close errors
      }
      audioContextRef.current = null;
    }

    if (updateVolume) {
      setVolume(0);
    }
  };

  /**
   * Convert ArrayBuffer (Int16 PCM) to Base64
   */
  const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    const chunkSize = 0x8000;

    for (let i = 0; i < bytes.length; i += chunkSize) {
      const chunk = bytes.subarray(i, i + chunkSize);
      binary += String.fromCharCode(...chunk);
    }

    return btoa(binary);
  };

  const startRecording = async () => {
    // Prevent multiple concurrent starts
    if (startingRef.current) {
      return;
    }
    startingRef.current = true;

    try {
      if (!window.AudioContext) {
        throw new Error('当前浏览器不支持 AudioWorklet，请使用新版 Chrome/Edge');
      }

      // Step 1: Get microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: TARGET_SAMPLE_RATE,
        },
      });

      // Check if unmounted during async operation
      if (!mountedRef.current) {
        stream.getTracks().forEach(track => track.stop());
        startingRef.current = false;
        return;
      }
      mediaStreamRef.current = stream;

      // Step 2: Initialize VAD with shared stream
      if (!window.vad || !window.vad.MicVAD) {
        throw new Error('VAD library not loaded. Please refresh the page.');
      }

      const vadInstance = await window.vad.MicVAD.new({
        getStream: async () => stream,
        onnxWASMBasePath: 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/',
        baseAssetPath: 'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.29/dist/',
        onSpeechStart: () => {
          if (mountedRef.current) {
            onSpeechStart?.();
          }
        },
        onSpeechEnd: () => {
          if (mountedRef.current) {
            onSpeechEnd?.();
          }
        },
      });
      vadRef.current = vadInstance;
      await vadInstance.start();

      // Check if unmounted during async operation
      if (!mountedRef.current) {
        cleanupRecordingResources(false);
        startingRef.current = false;
        return;
      }

      // Step 3: Create AudioContext
      const audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
      if (!audioContext.audioWorklet) {
        await audioContext.close();
        throw new Error('当前浏览器不支持 AudioWorklet，请使用新版 Chrome/Edge');
      }
      const source = audioContext.createMediaStreamSource(stream);

      // Step 4: Create Analyser for volume monitoring
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      audioContextRef.current = audioContext;
      analyserRef.current = analyser;

      // Volume monitoring
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      intervalRef.current = setInterval(() => {
        if (!mountedRef.current || !analyserRef.current) {
          return;
        }
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        setVolume(average);
      }, 100);

      // Step 5: Load AudioWorklet processor
      const workletPath = '/audio-worklet/pcm-processor.js';
      await audioContext.audioWorklet.addModule(workletPath);

      // Check if unmounted during async operation
      if (!mountedRef.current) {
        cleanupRecordingResources(false);
        startingRef.current = false;
        return;
      }

      // Step 6: Create AudioWorkletNode
      const workletNode = new AudioWorkletNode(audioContext, 'pcm-processor');
      workletNodeRef.current = workletNode;
      recordingActiveRef.current = true;

      // Handle audio chunks from worklet
      workletNode.port.onmessage = (event) => {
        if (!mountedRef.current || !recordingActiveRef.current || !workletNodeRef.current) {
          return;
        }
        const buffer = event.data as ArrayBuffer;
        const base64 = arrayBufferToBase64(buffer);
        onAudioData(base64);
      };

      // Step 7: Create gain node to prevent echo
      const gainNode = audioContext.createGain();
      gainNode.gain.value = 0; // Mute output
      gainNodeRef.current = gainNode;

      // Step 8: Connect audio processing chain
      source.connect(workletNode);
      workletNode.connect(gainNode);
      gainNode.connect(audioContext.destination);

      startingRef.current = false;
      if (mountedRef.current) {
        onRecordingChange(true);
      }

    } catch (error) {
      startingRef.current = false;
      cleanupRecordingResources(mountedRef.current);
      if (!mountedRef.current) {
        return;
      }
      console.error('Error accessing microphone:', error);
      const message = error instanceof Error ? error.message : '无法访问麦克风，请检查权限设置';
      alert(message);
    }
  };

  const stopRecording = () => {
    // Prevent stop during start
    startingRef.current = false;
    cleanupRecordingResources(mountedRef.current);
    // Only call onRecordingChange if we were recording
    if (isRecording) {
      onRecordingChange(false);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stopRecording();
    };
  }, []);

  useEffect(() => {
    if ((disabled || !isRecording) && recordingActiveRef.current) {
      cleanupRecordingResources(mountedRef.current);
      if (isRecording) {
        onRecordingChange(false);
      }
    }
  }, [disabled, isRecording, onRecordingChange]);

  const toggleRecording = () => {
    if (disabled && !isRecording) {
      return;
    }
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <div className="relative flex items-center justify-center">
      {/* Volume Ripple Effect when recording */}
      {isRecording && (
        <div
          className="absolute rounded-full border border-primary-500/50 pointer-events-none transition-all duration-75"
          style={{
            width: `${100 + (volume / 255) * 100}%`,
            height: `${100 + (volume / 255) * 100}%`,
            opacity: Math.max(0, 1 - (volume / 255) * 1.5),
          }}
        />
      )}

      {/* Record button */}
      <button
        data-testid="voice-recorder-toggle"
        onClick={toggleRecording}
        disabled={disabled && !isRecording}
        className={`
          relative z-10 w-16 h-16 rounded-full flex items-center justify-center
          transition-all duration-300 shadow-xl
          ${disabled && !isRecording ? 'opacity-50 cursor-not-allowed shadow-none' : ''}
          ${isRecording
            ? 'bg-primary-500 hover:bg-primary-600 shadow-primary-500/40'
            : 'bg-slate-700 hover:bg-slate-600 shadow-slate-900/50'
          }
        `}
        title={disabled && !isRecording ? '语音识别准备中' : isRecording ? '停止录音' : '开始说话'}
      >
        {isRecording ? (
          <Mic className="w-7 h-7 text-white" />
        ) : (
          <MicOff className="w-7 h-7 text-slate-300" />
        )}
      </button>
    </div>
  );
}
