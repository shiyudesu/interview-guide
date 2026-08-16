/**
 * AudioWorkletProcessor for PCM audio capture
 *
 * Responsibilities:
 * - Receives microphone input (Float32)
 * - Resamples to 16kHz target rate
 * - Converts Float32 to Int16 PCM
 * - Accumulates samples and sends 200ms chunks (3200 samples) via postMessage
 */
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.pending = [];
    this.pendingLength = 0;
    this.samplesPerChunk = 3200; // 200ms at 16kHz
  }

  /**
   * @param {Float32Array[]} inputs
   * @param {Float32Array[]} outputs
   * @param {Record<string, unknown>} parameters
   * @returns {boolean}
   */
  process(inputs, outputs, parameters) {
    const input = inputs[0]?.[0];
    if (!input || input.length === 0) {
      return true;
    }

    const resampled = this.resample(input, sampleRate, this.targetSampleRate);
    const pcm = this.float32ToInt16(resampled);
    this.enqueue(pcm);
    this.flushChunks();

    return true;
  }

  /**
   * Linear interpolation resampling
   * @param {Float32Array} input
   * @param {number} sourceRate
   * @param {number} targetRate
   * @returns {Float32Array}
   */
  resample(input, sourceRate, targetRate) {
    if (sourceRate === targetRate) {
      return input;
    }

    const ratio = sourceRate / targetRate;
    const outputLength = Math.max(1, Math.round(input.length / ratio));
    const output = new Float32Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const sourceIndex = i * ratio;
      const lower = Math.floor(sourceIndex);
      const upper = Math.min(lower + 1, input.length - 1);
      const weight = sourceIndex - lower;
      output[i] = input[lower] * (1 - weight) + input[upper] * weight;
    }

    return output;
  }

  /**
   * Convert Float32 to Int16 PCM
   * @param {Float32Array} input
   * @returns {Int16Array}
   */
  float32ToInt16(input) {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return output;
  }

  /**
   * Add PCM chunk to pending buffer
   * @param {Int16Array} pcm
   */
  enqueue(pcm) {
    this.pending.push(pcm);
    this.pendingLength += pcm.length;
  }

  /**
   * Flush complete chunks (200ms each) to main thread
   */
  flushChunks() {
    while (this.pendingLength >= this.samplesPerChunk && this.pending.length > 0) {
      const chunk = new Int16Array(this.samplesPerChunk);
      let offset = 0;

      while (offset < this.samplesPerChunk && this.pending.length > 0) {
        const head = this.pending[0];
        if (!head || head.length === 0) {
          this.pending.shift();
          continue;
        }

        const take = Math.min(head.length, this.samplesPerChunk - offset);
        chunk.set(head.subarray(0, take), offset);

        if (take === head.length) {
          this.pending.shift();
        } else {
          this.pending[0] = head.subarray(take);
        }

        offset += take;
        this.pendingLength -= take;
      }

      // Send chunk (clone mode to avoid transferable issues)
      try {
        this.port.postMessage(chunk.buffer);
      } catch (e) {
        // Ignore postMessage errors during shutdown
      }
    }

    // Reset if pending is empty but length is inconsistent
    if (this.pending.length === 0) {
      this.pendingLength = 0;
    }
  }
}

registerProcessor('pcm-processor', PcmProcessor);
